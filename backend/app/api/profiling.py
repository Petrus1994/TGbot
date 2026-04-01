from fastapi import APIRouter, HTTPException
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

router = APIRouter(prefix="/goals/{goal_id}/profiling", tags=["profiling"])

ai_profiling_service = AIProfilingService()


@router.post("/start", response_model=ProfilingStartResponse)
async def start_profiling_endpoint(goal_id: str):
    return await start_profiling(goal_id)


@router.get("/current-question", response_model=ProfilingQuestionResponse)
def get_current_question_endpoint(goal_id: str):
    return get_current_question(goal_id)


@router.post("/answer", response_model=ProfilingStateResponse)
def submit_profiling_answer_endpoint(goal_id: str, payload: ProfilingAnswerRequest):
    return submit_profiling_answer(goal_id, payload.answer)


@router.get("/state", response_model=ProfilingStateResponse)
def get_profiling_state_endpoint(goal_id: str):
    return get_profiling_state(goal_id)


@router.post("/ai-questions")
async def generate_ai_profiling_questions(goal_id: str):
    """
    Генерирует динамические profiling вопросы через AI.
    Полезно для отладки и сравнения, но основной flow уже использует AI внутри /start.
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
        raise HTTPException(status_code=404, detail="goal_not_found")

    try:
        result = await ai_profiling_service.generate_questions(goal["title"])
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"ai_profiling_failed: {str(e)}",
        ) from e