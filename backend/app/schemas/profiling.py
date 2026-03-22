from pydantic import BaseModel


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
    answer: str


class ProfilingStateResponse(BaseModel):
    goal_id: str
    state: str
    substate: str | None = None
    questions_answered_count: int
    questions_total_count: int
    current_question_key: str | None = None
    current_question_text: str | None = None
    is_completed: bool
    answers: dict