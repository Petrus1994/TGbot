from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text

from app.db import engine
from app.services.dynamic_profiling_service import DynamicProfilingService
from app.services.profiling_quality_service import ProfilingQualityService
from app.services.profiling_summary_service import ProfilingSummaryService


dynamic_profiling_service = DynamicProfilingService()
profiling_quality_service = ProfilingQualityService()
profiling_summary_service = ProfilingSummaryService()

REQUIRED_PROFILING_KEYS = (
    "current_level",
    "constraints",
    "resources",
    "motivation",
    "coach_style",
)

MAX_FOLLOW_UP_ATTEMPTS_PER_QUESTION = 2


# =========================
# HELPERS
# =========================

def _normalize_context(context: Any) -> dict:
    return context if isinstance(context, dict) else {}


def _get_block(context: dict) -> dict:
    return context.get("profiling", {}) or {}


def _get_questions(context):
    return _get_block(context).get("questions", []) or []


def _get_answers(context):
    raw = _get_block(context).get("answers", {})
    return {k: str(v).strip() for k, v in raw.items() if str(v).strip()}


def _get_current_key(context):
    return _get_block(context).get("current_question_key")


def _find_q(questions, key):
    return next((q for q in questions if q.get("key") == key), None)


def _apply(connection, goal_id, state, substate, context):
    connection.execute(
        text(
            """
            UPDATE goal_sessions
            SET state=:state,
                substate=:substate,
                context_json=CAST(:ctx AS jsonb),
                updated_at=NOW()
            WHERE goal_id=:goal_id
            """
        ),
        {
            "goal_id": goal_id,
            "state": state,
            "substate": substate,
            "ctx": json.dumps(context, ensure_ascii=False),
        },
    )


def _response(goal_id, state, substate, context, extra=None):
    questions = _get_questions(context)
    answers = _get_answers(context)
    key = _get_current_key(context)
    q = _find_q(questions, key)

    base = {
        "goal_id": goal_id,
        "state": state,
        "substate": substate,
        "questions_answered_count": len(answers),
        "questions_total_count": len(questions),
        "current_question_key": key,
        "current_question_text": q.get("text") if q else None,
        "example_answer": q.get("example_answer") if q else None,
        "is_completed": _get_block(context).get("is_completed", False),
        "answers": answers,
        "profiling_summary": _get_block(context).get("summary"),
    }

    if extra:
        base.update(extra)

    return base


def _missing_required(answers):
    return [k for k in REQUIRED_PROFILING_KEYS if k not in answers]


# =========================
# START
# =========================

async def start_profiling(goal_id: str) -> dict:
    with engine.begin() as conn:
        goal = conn.execute(
            text("SELECT id,user_id,title,description FROM goals WHERE id=:id"),
            {"id": goal_id},
        ).mappings().first()

        if not goal:
            raise HTTPException(404, "goal_not_found")

        context = await dynamic_profiling_service.build_context(
            goal["title"], goal.get("description")
        )

        context = _normalize_context(context)
        profiling = context.get("profiling", {})
        questions = profiling.get("questions", [])

        if not questions:
            raise HTTPException(500, "questions_not_generated")

        first = questions[0]

        profiling.update({
            "current_question_key": first["key"],
            "answers": {},
            "asked_question_keys": [],
            "follow_up_attempts": {},
            "is_completed": False,
            "summary": None,
        })

        context["profiling"] = profiling

        _apply(conn, goal_id, "awaiting_profiling_answer", first["key"], context)

        return _response(goal_id, "awaiting_profiling_answer", first["key"], context)


# =========================
# ANSWER
# =========================

async def submit_profiling_answer(goal_id: str, answer: str) -> dict:
    answer = answer.strip()
    if not answer:
        raise HTTPException(400, "empty_answer")

    with engine.begin() as conn:
        session = conn.execute(
            text("SELECT * FROM goal_sessions WHERE goal_id=:id"),
            {"id": goal_id},
        ).mappings().first()

        context = _normalize_context(session["context_json"])
        profiling = _get_block(context)
        questions = _get_questions(context)
        answers = _get_answers(context)

        key = _get_current_key(context)
        q = _find_q(questions, key)

        if not q:
            raise HTTPException(500, "question_not_found")

        # ===== AI ОЦЕНКА =====
        try:
            eval_result = await profiling_quality_service.evaluate_answer(
                goal_title="",
                goal_description=None,
                question=q,
                answer=answer,
                answers=answers,
            )
        except Exception:
            eval_result = {"accepted": True}

        # ===== НЕ ПРИНЯТ =====
        if not eval_result.get("accepted"):
            attempts = profiling.get("follow_up_attempts", {})
            count = attempts.get(key, 0) + 1
            attempts[key] = count
            profiling["follow_up_attempts"] = attempts
            context["profiling"] = profiling

            _apply(conn, goal_id, session["state"], session["substate"], context)

            return _response(
                goal_id,
                session["state"],
                session["substate"],
                context,
                extra={
                    "answer_accepted": False,
                    "needs_follow_up": True,
                    "feedback_message": eval_result.get("feedback_message"),
                    "follow_up_question": eval_result.get("follow_up_question"),
                },
            )

        # ===== ПРИНЯТ =====
        answers[key] = answer
        profiling["answers"] = answers

        # ===== NEXT STEP (AI) =====
        try:
            next_step = await dynamic_profiling_service.select_next_step(
                goal_title="",
                goal_description=None,
                questions=questions,
                answers=answers,
                asked_question_keys=list(answers.keys()),
                skipped_question_keys=[],
            )
        except Exception:
            next_step = {"is_completed": False, "next_question_key": None}

        is_completed = next_step.get("is_completed", False)

        # ===== FORCE REQUIRED =====
        if is_completed and _missing_required(answers):
            forced = next(
                (q for q in questions if q["key"] in _missing_required(answers)),
                None,
            )

            if forced:
                profiling["current_question_key"] = forced["key"]
                context["profiling"] = profiling

                _apply(conn, goal_id, "awaiting_profiling_answer", forced["key"], context)

                return _response(
                    goal_id,
                    "awaiting_profiling_answer",
                    forced["key"],
                    context,
                    extra={"answer_accepted": True},
                )

        # ===== FINAL =====
        if is_completed:
            summary = await profiling_summary_service.build_summary(
                goal_title="",
                goal_description=None,
                answers=answers,
            )

            profiling["is_completed"] = True
            profiling["summary"] = summary
            profiling["current_question_key"] = None

            context["profiling"] = profiling

            _apply(conn, goal_id, "idle", "profiling_completed", context)

            return _response(
                goal_id,
                "idle",
                "profiling_completed",
                context,
                extra={"answer_accepted": True},
            )

        # ===== NEXT QUESTION =====
        next_key = next_step.get("next_question_key")
        next_q = _find_q(questions, next_key)

        if not next_q:
            next_q = next((q for q in questions if q["key"] not in answers), None)

        if not next_q:
            raise HTTPException(500, "next_question_not_found")

        profiling["current_question_key"] = next_q["key"]
        context["profiling"] = profiling

        _apply(conn, goal_id, "awaiting_profiling_answer", next_q["key"], context)

        return _response(
            goal_id,
            "awaiting_profiling_answer",
            next_q["key"],
            context,
            extra={"answer_accepted": True},
        )


# =========================
# STATE
# =========================

def get_profiling_state(goal_id: str) -> dict:
    with engine.begin() as conn:
        session = conn.execute(
            text("SELECT * FROM goal_sessions WHERE goal_id=:id"),
            {"id": goal_id},
        ).mappings().first()

        context = _normalize_context(session["context_json"])

        return _response(goal_id, session["state"], session["substate"], context)


def get_profiling_answers(goal_id: str) -> dict:
    with engine.begin() as conn:
        session = conn.execute(
            text("SELECT context_json FROM goal_sessions WHERE goal_id=:id"),
            {"id": goal_id},
        ).mappings().first()

        return _get_answers(_normalize_context(session["context_json"]))