from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import text

from app.db import engine


PROFILING_QUESTIONS = [
    {
        "key": "current_level",
        "text": "Какой у тебя сейчас уровень в этой цели?",
    },
    {
        "key": "constraints",
        "text": "Какие у тебя есть ограничения: время, здоровье, деньги, условия?",
    },
    {
        "key": "resources",
        "text": "Какие у тебя есть ресурсы: инструменты, материалы, оборудование, наставник?",
    },
    {
        "key": "motivation",
        "text": "Почему для тебя важна эта цель?",
    },
    {
        "key": "time_budget",
        "text": "Сколько времени в день или неделю ты готов уделять этой цели?",
    },
    {
        "key": "coach_style",
        "text": "Какой стиль коучинга тебе подходит? aggressive / balanced / soft / или опиши свой вариант.",
    },
]


def _get_goal(connection, goal_id: str):
    goal = connection.execute(
        text(
            """
            SELECT id, user_id, status
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


def _build_state_response(goal_id: str, state: str, substate: str | None, context: dict):
    answers = context.get("answers", {})
    current_question_index = context.get("current_question_index", 0)
    questions_total_count = len(PROFILING_QUESTIONS)
    questions_answered_count = len(answers)
    is_completed = current_question_index >= questions_total_count

    current_question_key = None
    current_question_text = None

    if not is_completed:
        current_question_key = PROFILING_QUESTIONS[current_question_index]["key"]
        current_question_text = PROFILING_QUESTIONS[current_question_index]["text"]

    return {
        "goal_id": goal_id,
        "state": state,
        "substate": substate,
        "questions_answered_count": questions_answered_count,
        "questions_total_count": questions_total_count,
        "current_question_key": current_question_key,
        "current_question_text": current_question_text,
        "is_completed": is_completed,
        "answers": answers,
    }


def start_profiling(goal_id: str) -> dict:
    with engine.begin() as connection:
        goal = _get_goal(connection, goal_id)

        context = {
            "answers": {},
            "current_question_index": 0,
        }

        first_question = PROFILING_QUESTIONS[0]

        connection.execute(
            text(
                """
                UPDATE goals
                SET
                    status = 'profiling',
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
                "context_json": json.dumps(context),
            },
        )

        return {
            "goal_id": goal_id,
            "state": "awaiting_profiling_answer",
            "substate": first_question["key"],
            "current_question_key": first_question["key"],
            "current_question_text": first_question["text"],
            "questions_answered_count": 0,
            "questions_total_count": len(PROFILING_QUESTIONS),
            "is_completed": False,
        }


def get_current_question(goal_id: str) -> dict:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = session["context_json"] or {}

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
            "questions_answered_count": result["questions_answered_count"],
            "questions_total_count": result["questions_total_count"],
            "is_completed": result["is_completed"],
        }


def submit_profiling_answer(goal_id: str, answer: str) -> dict:
    cleaned_answer = answer.strip()
    if not cleaned_answer:
        raise HTTPException(status_code=400, detail="empty_answer")

    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = session["context_json"] or {}

        current_question_index = context.get("current_question_index", 0)
        answers = context.get("answers", {})

        if current_question_index >= len(PROFILING_QUESTIONS):
            raise HTTPException(status_code=400, detail="profiling_already_completed")

        current_question = PROFILING_QUESTIONS[current_question_index]
        answers[current_question["key"]] = cleaned_answer

        next_index = current_question_index + 1
        is_completed = next_index >= len(PROFILING_QUESTIONS)

        new_context = {
            "answers": answers,
            "current_question_index": next_index,
        }

        if is_completed:
            new_state = "idle"
            new_substate = "profiling_completed"

            connection.execute(
                text(
                    """
                    UPDATE goals
                    SET
                        status = 'planning',
                        updated_at = NOW()
                    WHERE id = :goal_id
                    """
                ),
                {"goal_id": goal_id},
            )
        else:
            new_state = "awaiting_profiling_answer"
            new_substate = PROFILING_QUESTIONS[next_index]["key"]

        connection.execute(
            text(
                """
                UPDATE goal_sessions
                SET
                    state = :state,
                    substate = :substate,
                    context_json = CAST(:context_json AS jsonb),
                    updated_at = NOW()
                WHERE goal_id = :goal_id
                """
            ),
            {
                "goal_id": goal_id,
                "state": new_state,
                "substate": new_substate,
                "context_json": json.dumps(new_context),
            },
        )

        return _build_state_response(
            goal_id=goal_id,
            state=new_state,
            substate=new_substate,
            context=new_context,
        )


def get_profiling_state(goal_id: str) -> dict:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = session["context_json"] or {}

        return _build_state_response(
            goal_id=goal_id,
            state=session["state"],
            substate=session["substate"],
            context=context,
        )


def get_profiling_answers(goal_id: str) -> dict[str, str]:
    with engine.begin() as connection:
        session = _get_goal_session(connection, goal_id)
        context = session["context_json"] or {}
        answers = context.get("answers", {})

        if not isinstance(answers, dict):
            return {}

        return {str(key): str(value) for key, value in answers.items()}