from pydantic import BaseModel, Field


class ProfilingStartResponse(BaseModel):
    goal_id: str
    state: str
    substate: str
    current_question_key: str
    current_question_text: str
    questions_answered_count: int
    questions_total_count: int
    is_completed: bool


class ProfilingQuestionResponse(BaseModel):
    goal_id: str
    current_question_key: str | None = None
    current_question_text: str | None = None
    questions_answered_count: int
    questions_total_count: int
    is_completed: bool


class ProfilingAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


class ProfilingStateResponse(BaseModel):
    goal_id: str
    state: str
    substate: str | None = None
    questions_answered_count: int
    questions_total_count: int
    current_question_key: str | None = None
    current_question_text: str | None = None
    is_completed: bool
    answers: dict[str, str] = Field(default_factory=dict)