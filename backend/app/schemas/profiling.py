from pydantic import BaseModel, Field


# ======================
# START RESPONSE
# ======================
class ProfilingStartResponse(BaseModel):
    goal_id: str
    state: str
    substate: str

    current_question_key: str
    current_question_text: str

    # NEW
    example_answer: str | None = None

    questions_answered_count: int
    questions_total_count: int

    is_completed: bool


# ======================
# CURRENT QUESTION
# ======================
class ProfilingQuestionResponse(BaseModel):
    goal_id: str

    current_question_key: str | None = None
    current_question_text: str | None = None

    # NEW
    example_answer: str | None = None

    questions_answered_count: int
    questions_total_count: int

    is_completed: bool


# ======================
# ANSWER REQUEST
# ======================
class ProfilingAnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)


# ======================
# MAIN STATE RESPONSE (KEY MODEL)
# ======================
class ProfilingStateResponse(BaseModel):
    goal_id: str

    state: str
    substate: str | None = None

    # progress
    questions_answered_count: int
    questions_total_count: int

    # current question
    current_question_key: str | None = None
    current_question_text: str | None = None

    # NEW (очень важно)
    example_answer: str | None = None

    # completion
    is_completed: bool

    # NEW — оценка ответа
    answer_accepted: bool | None = None
    needs_follow_up: bool | None = None

    # NEW — фидбек пользователю
    feedback_message: str | None = None
    follow_up_question: str | None = None

    # все ответы пользователя
    answers: dict[str, str] = Field(default_factory=dict)