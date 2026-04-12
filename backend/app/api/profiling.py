from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.db import engine
from app.schemas.profiling import (
    ProfilingAnswerRequest,
    ProfilingQuestionResponse,
    ProfilingStartResponse,
    ProfilingStateResponse,
)
from app.services.ai_profiling_service import AIProfilingService
from app.services.profiling_service import (
    get_current_question,
    get_profiling_state,
    start_profiling,
    submit_profiling_answer,
)

router = APIRouter(
    prefix="/goals/{goal_id}/profiling",
    tags=["profiling"],
)

ai_profiling_service = AIProfilingService()


@router.post(
    "/start",
    response_model=ProfilingStartResponse,
    status_code=status.HTTP_200_OK,
    summary="Start profiling flow for a goal",
)
async def start_profiling_endpoint(goal_id: str):
    try:
        return await start_profiling(goal_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="profiling_start_failed",
        )


@router.get(
    "/current-question",
    response_model=ProfilingQuestionResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current profiling question",
)
def get_current_question_endpoint(goal_id: str):
    try:
        return get_current_question(goal_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="get_current_question_failed",
        )


@router.post(
    "/answer",
    response_model=ProfilingStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit answer for current profiling question",
)
async def submit_profiling_answer_endpoint(
    goal_id: str,
    payload: ProfilingAnswerRequest,
):
    if not payload.answer or not payload.answer.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="empty_answer",
        )

    try:
        return await submit_profiling_answer(goal_id, payload.answer)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="submit_profiling_answer_failed",
        )


@router.get(
    "/state",
    response_model=ProfilingStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current profiling state",
)
def get_profiling_state_endpoint(goal_id: str):
    try:
        return get_profiling_state(goal_id)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="get_profiling_state_failed",
        )


@router.post(
    "/ai-questions",
    status_code=status.HTTP_200_OK,
    summary="Generate AI profiling questions (debug)",
)
async def generate_ai_profiling_questions(goal_id: str):
    """
    Debug endpoint.
    Не используется в основном flow.
    """

    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                SELECT id, title, description
                FROM goals
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

    if not goal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="goal_not_found",
        )

    try:
        result = await ai_profiling_service.generate_questions(goal["title"])

        return {
            "goal_id": goal_id,
            "goal_title": goal["title"],
            "goal_description": goal.get("description"),
            "questions": result.get("questions", []),
            "coach_message": result.get("coach_message"),
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ai_profiling_failed",
        )