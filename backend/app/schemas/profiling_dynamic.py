from pydantic import BaseModel, Field


class GoalAnalysisSchema(BaseModel):
    goal_type: str
    difficulty: str
    time_horizon: str | None = None
    profiling_focus: list[str] = Field(default_factory=list)


class ProfilingQuestionSchema(BaseModel):
    id: str
    key: str
    text: str


class ProfilingQuestionListSchema(BaseModel):
    questions: list[ProfilingQuestionSchema]