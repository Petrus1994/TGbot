from fastapi import APIRouter
from app.schemas.profiling import (
    ProfilingStartResponse,
    ProfilingQuestionResponse,
    ProfilingAnswerRequest,
    ProfilingStateResponse,
)
from app.services.profiling_service import (
    start_profiling,
    get_current_question,
    submit_profiling_answer,
    get_profiling_state,
)

router = APIRouter(prefix="/goals/{goal_id}/profiling", tags=["profiling"])


@router.post("/start", response_model=ProfilingStartResponse)
def start_profiling_endpoint(goal_id: str):
    return start_profiling(goal_id)


@router.get("/current-question", response_model=ProfilingQuestionResponse)
def get_current_question_endpoint(goal_id: str):
    return get_current_question(goal_id)


@router.post("/answer", response_model=ProfilingStateResponse)
def submit_profiling_answer_endpoint(goal_id: str, payload: ProfilingAnswerRequest):
    return submit_profiling_answer(goal_id, payload.answer)


@router.get("/state", response_model=ProfilingStateResponse)
def get_profiling_state_endpoint(goal_id: str):
    return get_profiling_state(goal_id)