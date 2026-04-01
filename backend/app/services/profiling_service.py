from __future__ import annotations

import json

from fastapi import HTTPException
from sqlalchemy import text

from app.db import engine
from app.services.dynamic_profiling_service import DynamicProfilingService


FALLBACK_PROFILING_QUESTIONS = [
    {
        "id": "q1",
        "key": "current_level",
        "text": "Какой у тебя сейчас уровень в этой цели?",
    },
    {
        "id": "q2",
        "key": "constraints",
        "text": "Какие у тебя есть ограничения: время, здоровье, деньги, условия?",
    },
    {
        "id": "q3",
        "key": "resources",
        "text": "Какие у тебя есть ресурсы: инструменты, материалы, оборудование, наставник?",
    },
    {
        "id": "q4",
        "key": "motivation",
        "text": "Почему для тебя важна эта цель?",
    },
    {
        "id": "q5",
        "key": "time_budget",
        "text": "Сколько времени в день или неделю ты готов уделять этой цели?",
    },
    {
        "id": "q6",
        "key": "coach_style",
        "text": "Какой стиль коучинга тебе подходит? aggressive / balanced / soft / или опиши свой вариант.",
    },
]

dynamic_profiling_service = DynamicProfilingService()


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


def _normalize_context(context: dict | None) -> dict:
    if not isinstance(context, dict):
        return {}
    return context


def _get_profiling_block(context: dict) -> dict:
    context = _normalize_context(context)
    profiling = context.get("profiling", {})
    if not isinstance(profiling, dict):
        profiling = {}
    return profiling


def _get_questions(context: dict) -> list[dict]:
    profiling = _get_profiling_block(context)
    questions = profiling.get("questions", [])
    if not isinstance(questions, list) or not questions:
        return FALLBACK_PROFILING_QUESTIONS
    return questions


def _get_answers(context: dict) -> dict[str, str]:
    profiling = _get_profiling_block(context)
    answers = profiling.get("answers", {})
    if not isinstance(answers, dict):
        return {}
    return {str(key): str(value) for key, value in answers.items()}


def _build_fallback_context() -> dict:
    return {
        "profiling": {
            "mode": "fallback_fixed",
            "goal_analysis": {
                "goal_type": "custom",
                "difficulty": "medium",
                "time_horizon": None,
                "profiling_focus": [
                    "current_level",
                    "constraints",
                    "resources",
                    "motivation",
                    "time_budget",
                    "coach_style",
                ],
            },
            "questions": FALLBACK_PROFILING_QUESTIONS,
            "answers": {},
            "current_question_index": 0,
            "is_completed": False,
            "questions_total_count": len(FALLBACK_PROFILING_QUESTIONS),
            "questions_answered_count": 0,
        }
    }


def _build_state_response(goal_id: str, state: str, substate: str | None, context: dict):
    profiling = _get_profiling_block(context)
    questions = _get_questions(context)
    answers = _get_answers(context)

    current_question_index = profiling.get("current_question_index", 0)
    if not isinstance(current_question_index, int):
        current_question_index = 0

    questions_total_count = len(questions)
    questions_answered_count = len(answers)
    is_completed = current_question_index >= questions_total_count

    current_question_key = None
    current_question_text = None

    if not is_completed:
        current_question = questions[current_question_index]
        current_question_key = current_question.get("key")
        current_question_text = current_question.get("text")

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


async def start_profiling(goal_id: str) -> dict:
    with engine.begin() as connection:
        goal = _get_goal(connection, goal_id)

        try:
            context = await dynamic_profiling_service.build_context(
                goal_title=goal["title"],
                goal_description=goal.get("description"),
            )
            print(f"✅ DYNAMIC PROFILING CONTEXT GENERATED FOR GOAL {goal_id}")
        except Exception as e:
            print(f"❌ DYNAMIC PROFILING GENERATION FAILED: {repr(e)}")
            context = _build_fallback_context()

        profiling = _get_profiling_block(context)
        questions = _get_questions(context)

        if not questions:
            context = _build_fallback_context()
            profiling = _get_profiling_block(context)
            questions = _get_questions(context)

        first_question = questions[0]

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
                "context_json": json.dumps(context, ensure_ascii=False),
            },
        )

        return {
            "goal_id": goal_id,
            "state": "awaiting_profiling_answer",
            "substate": first_question["key"],
            "current_question_key": first_question["key"],
            "current_question_text": first_question["text"],
            "questions_answered_count": profiling.get("questions_answered_count", 0),
            "questions_total_count": profiling.get("questions_total_count", len(questions)),
            "is_completed": False,
        }


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
        context = _normalize_context(session["context_json"])

        profiling = _get_profiling_block(context)
        questions = _get_questions(context)
        answers = _get_answers(context)

        current_question_index = profiling.get("current_question_index", 0)
        if not isinstance(current_question_index, int):
            current_question_index = 0

        if current_question_index >= len(questions):
            raise HTTPException(status_code=400, detail="profiling_already_completed")

        current_question = questions[current_question_index]
        answers[current_question["key"]] = cleaned_answer

        next_index = current_question_index + 1
        is_completed = next_index >= len(questions)

        new_profiling = {
            **profiling,
            "questions": questions,
            "answers": answers,
            "current_question_index": next_index,
            "is_completed": is_completed,
            "questions_total_count": len(questions),
            "questions_answered_count": len(answers),
        }

        new_context = {
            **context,
            "profiling": new_profiling,
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
            new_substate = questions[next_index]["key"]

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
                "context_json": json.dumps(new_context, ensure_ascii=False),
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