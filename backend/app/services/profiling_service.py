from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import text

from app.db import engine
from app.services.dynamic_profiling_service import DynamicProfilingService
from app.services.profiling_quality_service import ProfilingQualityService


dynamic_profiling_service = DynamicProfilingService()
profiling_quality_service = ProfilingQualityService()


def _get_goal(connection, goal_id: str):
    goal = connection.execute(
        text(
            """
            SELECT id, user_id, title, description, status
            FROM goals
            WHERE id = :goal_id
            """
        ),
        {"goal_id": goal_id},
    ).mappings().first()

    if not goal:
        raise HTTPException(status_code=404, detail="goal_not_found")

    return goal


def _get_goal_session(connection, goal_id: str):
    session = connection.execute(
        text(
            """
            SELECT goal_id, state, substate, context_json
            FROM goal_sessions
            WHERE goal_id = :goal_id
            """
        ),
        {"goal_id": goal_id},
    ).mappings().first()

    if not session:
        raise HTTPException(status_code=404, detail="goal_session_not_found")

    return session


def _normalize_context(context):
    return context if isinstance(context, dict) else {}


def _get_profiling_block(context):
    profiling = context.get("profiling", {})
    return profiling if isinstance(profiling, dict) else {}


def _get_questions(context):
    profiling = _get_profiling_block(context)
    questions = profiling.get("questions", [])
    return questions if isinstance(questions, list) else []


def _get_answers(context):
    profiling = _get_profiling_block(context)
    answers = profiling.get("answers", {})
    if not isinstance(answers, dict):
        return {}
    return {str(k): str(v) for k, v in answers.items()}


def _get_asked_question_keys(context):
    profiling = _get_profiling_block(context)
    keys = profiling.get("asked_question_keys", [])
    if not isinstance(keys, list):
        return []
    return [str(x) for x in keys]


def _get_skipped_question_keys(context):
    profiling = _get_profiling_block(context)
    keys = profiling.get("skipped_question_keys", [])
    if not isinstance(keys, list):
        return []
    return [str(x) for x in keys]


def _get_current_question_key(context):
    profiling = _get_profiling_block(context)
    value = profiling.get("current_question_key")
    return str(value) if value else None


def _find_question_by_key(questions: list[dict], question_key: str | None) -> dict | None:
    if not question_key:
        return None
    for question in questions:
        if question.get("key") == question_key:
            return question
    return None


def _build_state_response(goal_id, state, substate, context, extra=None):
    profiling = _get_profiling_block(context)
    questions = _get_questions(context)
    answers = _get_answers(context)
    current_question_key = _get_current_question_key(context)
    current_question = _find_question_by_key(questions, current_question_key)

    is_completed = bool(profiling.get("is_completed", False))

    response = {
        "goal_id": goal_id,
        "state": state,
        "substate": substate,
        "questions_answered_count": len(answers),
        "questions_total_count": len(questions),
        "current_question_key": current_question.get("key") if current_question else None,
        "current_question_text": current_question.get("text") if current_question else None,
        "example_answer": current_question.get("example_answer") if current_question else None,
        "is_completed": is_completed,
        "answers": answers,
    }

    if extra:
        response.update(extra)

    return response


async def start_profiling(goal_id: str) -> dict:
    with engine.begin() as connection:
        goal = _get_goal(connection, goal_id)

        try:
            context = await dynamic_profiling_service.build_context(
                goal_title=goal["title"],
                goal_description=goal.get("description"),
            )
        except Exception:
            raise HTTPException(status_code=500, detail="profiling_context_build_failed")

        profiling = _get_profiling_block(context)
        questions = _get_questions(context)

        if not questions:
            raise HTTPException(status_code=500, detail="profiling_questions_not_generated")

        first_question = questions[0]

        profiling["current_question_key"] = first_question["key"]
        profiling["asked_question_keys"] = []
        profiling["skipped_question_keys"] = []
        profiling["answers"] = {}
        profiling["is_completed"] = False
        profiling["questions_total_count"] = len(questions)
        profiling["questions_answered_count"] = 0
        context["profiling"] = profiling

        connection.execute(
            text(
                """
                UPDATE goals
                SET status = 'profiling',
                    updated_at = NOW()
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        )

        connection.execute(
            text(
                """
                INSERT INTO goal_sessions (
                    user_id,
                    goal_id,
                    state,
                    substate,
                    context_json
                )
                VALUES (
                    :user_id,
                    :goal_id,
                    'awaiting_profiling_answer',
                    :substate,
                    CAST(:context_json AS jsonb)
                )
                ON CONFLICT (goal_id)
                DO UPDATE SET
                    state = 'awaiting_profiling_answer',
                    substate = :substate,
                    context_json = CAST(:context_json AS jsonb),
                    updated_at = NOW()
                """
            ),
            {
                "user_id": goal["user_id"],
                "goal_id": goal_id,
                "substate": first_question["key"],
                "context_json": json.dumps(context, ensure_ascii=False),
            },
        )

        return _build_state_response(
            goal_id=goal_id,
            state="awaiting_profiling_answer",
            substate=first_question["key"],
            context=context,
        )


def get_current_question(goal_id: str) -> dict:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = _normalize_context(session["context_json"])

        result = _build_state_response(
            goal_id=goal_id,
            state=session["state"],
            substate=session["substate"],
            context=context,
        )

        return {
            "goal_id": result["goal_id"],
            "current_question_key": result["current_question_key"],
            "current_question_text": result["current_question_text"],
            "example_answer": result.get("example_answer"),
            "questions_answered_count": result["questions_answered_count"],
            "questions_total_count": result["questions_total_count"],
            "is_completed": result["is_completed"],
        }


async def submit_profiling_answer(goal_id: str, answer: str) -> dict:
    cleaned_answer = (answer or "").strip()
    if not cleaned_answer:
        raise HTTPException(status_code=400, detail="empty_answer")

    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        goal = _get_goal(connection, goal_id)
        context = _normalize_context(session["context_json"])

        profiling = _get_profiling_block(context)
        questions = _get_questions(context)
        answers = _get_answers(context)
        asked_question_keys = _get_asked_question_keys(context)
        skipped_question_keys = _get_skipped_question_keys(context)
        current_question_key = _get_current_question_key(context)

        if profiling.get("is_completed"):
            raise HTTPException(status_code=400, detail="profiling_already_completed")

        current_question = _find_question_by_key(questions, current_question_key)
        if not current_question:
            raise HTTPException(status_code=500, detail="current_question_not_found")

        evaluation = await profiling_quality_service.evaluate_answer(
            goal_title=goal["title"],
            goal_description=goal.get("description"),
            question=current_question,
            answer=cleaned_answer,
            answers=answers,
        )

        if not evaluation["accepted"]:
            return _build_state_response(
                goal_id,
                session["state"],
                session["substate"],
                context,
                extra={
                    "answer_accepted": False,
                    "needs_follow_up": True,
                    "feedback_message": evaluation.get("feedback_message"),
                    "follow_up_question": evaluation.get("follow_up_question"),
                    "example_answer": evaluation.get("example_answer"),
                },
            )

        answers[current_question["key"]] = cleaned_answer

        if current_question["key"] not in asked_question_keys:
            asked_question_keys.append(current_question["key"])

        next_step = await dynamic_profiling_service.select_next_step(
            goal_title=goal["title"],
            goal_description=goal.get("description"),
            questions=questions,
            answers=answers,
            asked_question_keys=asked_question_keys,
            skipped_question_keys=skipped_question_keys,
        )

        if next_step["is_completed"]:
            profiling.update(
                {
                    "answers": answers,
                    "asked_question_keys": asked_question_keys,
                    "skipped_question_keys": skipped_question_keys,
                    "current_question_key": None,
                    "is_completed": True,
                    "questions_answered_count": len(answers),
                    "questions_total_count": len(questions),
                }
            )
            context["profiling"] = profiling

            connection.execute(
                text(
                    """
                    UPDATE goals
                    SET status = 'planning',
                        updated_at = NOW()
                    WHERE id = :goal_id
                    """
                ),
                {"goal_id": goal_id},
            )

            connection.execute(
                text(
                    """
                    UPDATE goal_sessions
                    SET state = :state,
                        substate = :substate,
                        context_json = CAST(:context_json AS jsonb),
                        updated_at = NOW()
                    WHERE goal_id = :goal_id
                    """
                ),
                {
                    "goal_id": goal_id,
                    "state": "idle",
                    "substate": "profiling_completed",
                    "context_json": json.dumps(context, ensure_ascii=False),
                },
            )

            return _build_state_response(
                goal_id=goal_id,
                state="idle",
                substate="profiling_completed",
                context=context,
                extra={
                    "answer_accepted": True,
                    "needs_follow_up": False,
                },
            )

        next_question_key = next_step.get("next_question_key")
        next_question = _find_question_by_key(questions, next_question_key)

        if not next_question:
            raise HTTPException(status_code=500, detail="next_question_not_found")

        profiling.update(
            {
                "answers": answers,
                "asked_question_keys": asked_question_keys,
                "skipped_question_keys": skipped_question_keys,
                "current_question_key": next_question["key"],
                "is_completed": False,
                "questions_answered_count": len(answers),
                "questions_total_count": len(questions),
            }
        )
        context["profiling"] = profiling

        connection.execute(
            text(
                """
                UPDATE goal_sessions
                SET state = :state,
                    substate = :substate,
                    context_json = CAST(:context_json AS jsonb),
                    updated_at = NOW()
                WHERE goal_id = :goal_id
                """
            ),
            {
                "goal_id": goal_id,
                "state": "awaiting_profiling_answer",
                "substate": next_question["key"],
                "context_json": json.dumps(context, ensure_ascii=False),
            },
        )

        return _build_state_response(
            goal_id=goal_id,
            state="awaiting_profiling_answer",
            substate=next_question["key"],
            context=context,
            extra={
                "answer_accepted": True,
                "needs_follow_up": False,
            },
        )


def get_profiling_state(goal_id: str) -> dict:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = _normalize_context(session["context_json"])

        return _build_state_response(
            goal_id=goal_id,
            state=session["state"],
            substate=session["substate"],
            context=context,
        )


def get_profiling_answers(goal_id: str) -> dict[str, str]:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = _normalize_context(session["context_json"])
        return _get_answers(context)