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

SUMMARY_COMPLETENESS_KEYS = (
    "goal_outcome",
    "current_state",
    "constraints",
    "resources",
    "time_budget",
    "main_obstacles",
    "coach_style",
)

MAX_FOLLOW_UP_ATTEMPTS_PER_QUESTION = 2


def _get_goal(connection, goal_id: str):
    goal = connection.execute(
        text(
            """
            SELECT id, user_id, title, description, status, target_date
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


def _normalize_context(context: Any) -> dict[str, Any]:
    return context if isinstance(context, dict) else {}


def _get_profiling_block(context: dict[str, Any]) -> dict[str, Any]:
    profiling = context.get("profiling", {})
    return profiling if isinstance(profiling, dict) else {}


def _get_questions(context: dict[str, Any]) -> list[dict[str, Any]]:
    profiling = _get_profiling_block(context)
    questions = profiling.get("questions", [])
    return questions if isinstance(questions, list) else []


def _get_answers(context: dict[str, Any]) -> dict[str, str]:
    profiling = _get_profiling_block(context)
    answers = profiling.get("answers", {})
    if not isinstance(answers, dict):
        return {}
    return {str(k): str(v).strip() for k, v in answers.items() if str(v).strip()}


def _get_asked_question_keys(context: dict[str, Any]) -> list[str]:
    profiling = _get_profiling_block(context)
    keys = profiling.get("asked_question_keys", [])
    if not isinstance(keys, list):
        return []
    return [str(x) for x in keys if str(x).strip()]


def _get_skipped_question_keys(context: dict[str, Any]) -> list[str]:
    profiling = _get_profiling_block(context)
    keys = profiling.get("skipped_question_keys", [])
    if not isinstance(keys, list):
        return []
    return [str(x) for x in keys if str(x).strip()]


def _get_follow_up_attempts(context: dict[str, Any]) -> dict[str, int]:
    profiling = _get_profiling_block(context)
    attempts = profiling.get("follow_up_attempts", {})
    if not isinstance(attempts, dict):
        return {}

    normalized: dict[str, int] = {}
    for key, value in attempts.items():
        try:
            normalized[str(key)] = max(0, int(value))
        except Exception:
            normalized[str(key)] = 0
    return normalized


def _get_current_question_key(context: dict[str, Any]) -> str | None:
    profiling = _get_profiling_block(context)
    value = profiling.get("current_question_key")
    return str(value).strip() if value else None


def _get_summary(context: dict[str, Any]) -> dict[str, Any] | None:
    profiling = _get_profiling_block(context)
    summary = profiling.get("summary")
    return summary if isinstance(summary, dict) else None


def _find_question_by_key(
    questions: list[dict[str, Any]],
    question_key: str | None,
) -> dict[str, Any] | None:
    if not question_key:
        return None

    for question in questions:
        if question.get("key") == question_key:
            return question

    return None


def _normalize_text_field(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else None

    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            key_str = str(key).strip()
            item_str = str(item).strip()
            if key_str and item_str:
                parts.append(f"{key_str}: {item_str}")
        return "; ".join(parts) if parts else None

    value_str = str(value).strip()
    return value_str or None


def _has_required_answers(answers: dict[str, str]) -> bool:
    for key in REQUIRED_PROFILING_KEYS:
        value = answers.get(key)
        if not value or not str(value).strip():
            return False
    return True


def _get_missing_required_keys(answers: dict[str, str]) -> list[str]:
    missing_keys: list[str] = []

    for key in REQUIRED_PROFILING_KEYS:
        value = answers.get(key)
        if not value or not str(value).strip():
            missing_keys.append(key)

    return missing_keys


def _is_summary_complete(summary: dict[str, Any] | None) -> bool:
    if not isinstance(summary, dict):
        return False

    for key in SUMMARY_COMPLETENESS_KEYS:
        value = summary.get(key)
        normalized = _normalize_text_field(value)
        if not normalized:
            return False

    return True


def _extract_question_meta(question: dict[str, Any] | None) -> dict[str, Any]:
    if not question:
        return {
            "question_type": "text",
            "suggested_options": None,
            "allow_free_text": True,
        }

    question_type = str(question.get("question_type") or "text").strip()

    suggested_options = question.get("suggested_options")
    if not isinstance(suggested_options, list):
        suggested_options = None
    else:
        suggested_options = [
            str(option).strip()
            for option in suggested_options
            if str(option).strip()
        ] or None

    allow_free_text = question.get("allow_free_text")
    if not isinstance(allow_free_text, bool):
        allow_free_text = True

    return {
        "question_type": question_type,
        "suggested_options": suggested_options,
        "allow_free_text": allow_free_text,
    }


def _build_state_response(goal_id, state, substate, context, extra=None):
    profiling = _get_profiling_block(context)
    questions = _get_questions(context)
    answers = _get_answers(context)
    follow_up_attempts = _get_follow_up_attempts(context)
    current_question_key = _get_current_question_key(context)
    current_question = _find_question_by_key(questions, current_question_key)
    profiling_summary = _get_summary(context)

    is_completed = bool(profiling.get("is_completed", False))
    question_meta = _extract_question_meta(current_question)

    response = {
        "goal_id": goal_id,
        "state": state,
        "substate": substate,
        "questions_answered_count": len(answers),
        "questions_total_count": len(questions),
        "current_question_key": current_question.get("key") if current_question else None,
        "current_question_text": current_question.get("text") if current_question else None,
        "example_answer": current_question.get("example_answer") if current_question else None,
        "question_type": question_meta["question_type"],
        "suggested_options": question_meta["suggested_options"],
        "allow_free_text": question_meta["allow_free_text"],
        "follow_up_attempts": follow_up_attempts.get(current_question_key or "", 0),
        "is_completed": is_completed,
        "answers": answers,
        "profiling_summary": profiling_summary,
    }

    if extra:
        response.update(extra)

    return response


def _apply_profiling_update(
    connection,
    *,
    goal_id: str,
    state: str,
    substate: str | None,
    context: dict[str, Any],
) -> None:
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
            "state": state,
            "substate": substate,
            "context_json": json.dumps(context, ensure_ascii=False),
        },
    )


def _pick_forced_required_question(
    questions: list[dict[str, Any]],
    answers: dict[str, str],
    asked_question_keys: list[str],
) -> dict[str, Any] | None:
    missing_keys = _get_missing_required_keys(answers)

    for missing_key in missing_keys:
        candidate = _find_question_by_key(questions, missing_key)
        if candidate:
            return candidate

    for question in questions:
        key = str(question.get("key") or "").strip()
        if not key:
            continue
        if key in asked_question_keys:
            continue
        if key in REQUIRED_PROFILING_KEYS and key not in answers:
            return question

    return None


async def _build_and_validate_summary(
    *,
    goal_title: str,
    goal_description: str | None,
    answers: dict[str, str],
) -> dict[str, Any]:
    summary = await profiling_summary_service.build_summary(
        goal_title=goal_title,
        goal_description=goal_description,
        answers=answers,
    )

    if not isinstance(summary, dict):
        raise HTTPException(status_code=500, detail="profiling_summary_invalid")

    return summary


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

        context = _normalize_context(context)
        profiling = _get_profiling_block(context)
        questions = _get_questions(context)

        if not questions:
            raise HTTPException(status_code=500, detail="profiling_questions_not_generated")

        first_question = questions[0]

        profiling["current_question_key"] = first_question["key"]
        profiling["asked_question_keys"] = []
        profiling["skipped_question_keys"] = []
        profiling["follow_up_attempts"] = {}
        profiling["answers"] = {}
        profiling["summary"] = None
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
            "question_type": result.get("question_type"),
            "suggested_options": result.get("suggested_options"),
            "allow_free_text": result.get("allow_free_text"),
            "follow_up_attempts": result.get("follow_up_attempts"),
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
        follow_up_attempts = _get_follow_up_attempts(context)
        current_question_key = _get_current_question_key(context)

        if profiling.get("is_completed"):
            raise HTTPException(status_code=400, detail="profiling_already_completed")

        current_question = _find_question_by_key(questions, current_question_key)
        if not current_question:
            raise HTTPException(status_code=500, detail="current_question_not_found")

        try:
            evaluation = await profiling_quality_service.evaluate_answer(
                goal_title=goal["title"],
                goal_description=goal.get("description"),
                question=current_question,
                answer=cleaned_answer,
                answers=answers,
            )
        except Exception:
            raise HTTPException(status_code=500, detail="profiling_answer_evaluation_failed")

        if not isinstance(evaluation, dict):
            raise HTTPException(status_code=500, detail="profiling_answer_evaluation_invalid")

        if not evaluation.get("accepted"):
            current_attempts = follow_up_attempts.get(current_question["key"], 0) + 1
            follow_up_attempts[current_question["key"]] = current_attempts

            profiling["follow_up_attempts"] = follow_up_attempts
            context["profiling"] = profiling

            _apply_profiling_update(
                connection,
                goal_id=goal_id,
                state=session["state"],
                substate=session["substate"],
                context=context,
            )

            feedback_message = evaluation.get("feedback_message")
            follow_up_question = evaluation.get("follow_up_question")
            suggested_options = evaluation.get("suggested_options")

            if current_attempts >= MAX_FOLLOW_UP_ATTEMPTS_PER_QUESTION:
                if not suggested_options:
                    suggested_options = current_question.get("suggested_options")

                feedback_message = (
                    "Давай упростим. Можно выбрать самый близкий вариант или дать примерный, но полезный для плана ответ."
                )
                follow_up_question = (
                    follow_up_question
                    or "Выбери самый близкий вариант или ответь примерно, без идеальной точности."
                )

            return _build_state_response(
                goal_id,
                session["state"],
                session["substate"],
                context,
                extra={
                    "answer_accepted": False,
                    "needs_follow_up": True,
                    "feedback_message": feedback_message,
                    "follow_up_question": follow_up_question,
                    "example_answer": evaluation.get("example_answer"),
                    "suggested_options": suggested_options,
                    "follow_up_attempts": current_attempts,
                },
            )

        answers[current_question["key"]] = cleaned_answer

        if current_question["key"] not in asked_question_keys:
            asked_question_keys.append(current_question["key"])

        follow_up_attempts[current_question["key"]] = 0

        try:
            next_step = await dynamic_profiling_service.select_next_step(
                goal_title=goal["title"],
                goal_description=goal.get("description"),
                questions=questions,
                answers=answers,
                asked_question_keys=asked_question_keys,
                skipped_question_keys=skipped_question_keys,
            )
        except Exception:
            raise HTTPException(status_code=500, detail="profiling_next_step_selection_failed")

        if not isinstance(next_step, dict):
            raise HTTPException(status_code=500, detail="profiling_next_step_invalid")

        has_required_answers = _has_required_answers(answers)

        if next_step.get("is_completed") and not has_required_answers:
            forced_question = _pick_forced_required_question(
                questions=questions,
                answers=answers,
                asked_question_keys=asked_question_keys,
            )

            missing_keys = _get_missing_required_keys(answers)

            if not forced_question:
                raise HTTPException(
                    status_code=500,
                    detail=f"required_profiling_questions_missing_in_bank: {missing_keys}",
                )

            profiling.update(
                {
                    "answers": answers,
                    "asked_question_keys": asked_question_keys,
                    "skipped_question_keys": skipped_question_keys,
                    "follow_up_attempts": follow_up_attempts,
                    "current_question_key": forced_question["key"],
                    "is_completed": False,
                    "questions_answered_count": len(answers),
                    "questions_total_count": len(questions),
                    "summary": None,
                }
            )
            context["profiling"] = profiling

            _apply_profiling_update(
                connection,
                goal_id=goal_id,
                state="awaiting_profiling_answer",
                substate=forced_question["key"],
                context=context,
            )

            return _build_state_response(
                goal_id=goal_id,
                state="awaiting_profiling_answer",
                substate=forced_question["key"],
                context=context,
                extra={
                    "answer_accepted": True,
                    "needs_follow_up": False,
                    "feedback_message": "Нужно уточнить ещё несколько важных моментов, чтобы собрать сильный и точный план.",
                },
            )

        if next_step.get("is_completed"):
            summary = await _build_and_validate_summary(
                goal_title=goal["title"],
                goal_description=goal.get("description"),
                answers=answers,
            )

            if not _is_summary_complete(summary):
                forced_question = _pick_forced_required_question(
                    questions=questions,
                    answers=answers,
                    asked_question_keys=asked_question_keys,
                )

                if forced_question:
                    profiling.update(
                        {
                            "answers": answers,
                            "asked_question_keys": asked_question_keys,
                            "skipped_question_keys": skipped_question_keys,
                            "follow_up_attempts": follow_up_attempts,
                            "current_question_key": forced_question["key"],
                            "is_completed": False,
                            "questions_answered_count": len(answers),
                            "questions_total_count": len(questions),
                            "summary": None,
                        }
                    )
                    context["profiling"] = profiling

                    _apply_profiling_update(
                        connection,
                        goal_id=goal_id,
                        state="awaiting_profiling_answer",
                        substate=forced_question["key"],
                        context=context,
                    )

                    return _build_state_response(
                        goal_id=goal_id,
                        state="awaiting_profiling_answer",
                        substate=forced_question["key"],
                        context=context,
                        extra={
                            "answer_accepted": True,
                            "needs_follow_up": False,
                            "feedback_message": "Почти готово, но для точного плана не хватает ещё одного важного блока.",
                        },
                    )

                raise HTTPException(
                    status_code=500,
                    detail="profiling_summary_incomplete_and_no_forced_question_available",
                )

            profiling.update(
                {
                    "answers": answers,
                    "asked_question_keys": asked_question_keys,
                    "skipped_question_keys": skipped_question_keys,
                    "follow_up_attempts": follow_up_attempts,
                    "current_question_key": None,
                    "is_completed": True,
                    "questions_answered_count": len(answers),
                    "questions_total_count": len(questions),
                    "summary": summary,
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

            _apply_profiling_update(
                connection,
                goal_id=goal_id,
                state="idle",
                substate="profiling_completed",
                context=context,
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
                "follow_up_attempts": follow_up_attempts,
                "current_question_key": next_question["key"],
                "is_completed": False,
                "questions_answered_count": len(answers),
                "questions_total_count": len(questions),
                "summary": None,
            }
        )
        context["profiling"] = profiling

        _apply_profiling_update(
            connection,
            goal_id=goal_id,
            state="awaiting_profiling_answer",
            substate=next_question["key"],
            context=context,
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