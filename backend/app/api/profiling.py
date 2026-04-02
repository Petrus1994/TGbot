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


# ======================
# START
# ======================
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"profiling_start_failed: {str(e)}",
        ) from e


# ======================
# CURRENT QUESTION
# ======================
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"get_current_question_failed: {str(e)}",
        ) from e


# ======================
# ANSWER (UPDATED TO ASYNC)
# ======================
@router.post(
    "/answer",
    response_model=ProfilingStateResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit answer for current profiling question",
)
async def submit_profiling_answer_endpoint(goal_id: str, payload: ProfilingAnswerRequest):
    """
    Ключевой endpoint profiling v2.

    Поведение:
    - вызывает AI judge
    - если ответ слабый → НЕ двигает дальше
    - если ответ хороший → сохраняет и идёт дальше

    ВАЖНО:
    Бот должен проверять:
    - needs_follow_up
    """

    try:
        return await submit_profiling_answer(goal_id, payload.answer)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"submit_profiling_answer_failed: {str(e)}",
        ) from e


# ======================
# STATE
# ======================
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"get_profiling_state_failed: {str(e)}",
        ) from e


# ======================
# DEBUG: AI QUESTIONS
# ======================
@router.post(
    "/ai-questions",
    status_code=status.HTTP_200_OK,
    summary="Generate AI profiling questions for debugging",
)
async def generate_ai_profiling_questions(goal_id: str):
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
            "questions": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ai_profiling_failed: {str(e)}",
        ) from e