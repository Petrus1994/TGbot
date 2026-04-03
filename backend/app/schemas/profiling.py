from pydantic import BaseModel, Field


class ProfilingStartResponse(BaseModel):
    goal_id: str
    state: str
    substate: str

    current_question_key: str
    current_question_text: str

    example_answer: str | None = None

    questions_answered_count: int
    questions_total_count: int

    is_completed: bool


class ProfilingQuestionResponse(BaseModel):
    goal_id: str

    current_question_key: str | None = None
    current_question_text: str | None = None

    example_answer: str | None = None

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

    example_answer: str | None = None

    is_completed: bool

    answer_accepted: bool | None = None
    needs_follow_up: bool | None = None

    feedback_message: str | None = None
    follow_up_question: str | None = None

    answers: dict[str, str] = Field(default_factory=dict)

    profiling_summary: dict | None = None