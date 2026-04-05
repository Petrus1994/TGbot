from datetime import date, datetime

from pydantic import BaseModel, Field

from app.models.daily_plan import DailyPlanStatus
from app.models.daily_task import DailyTaskStatus


class DailyTaskStepResponse(BaseModel):
    order: int
    title: str
    instruction: str
    duration_minutes: int | None = None
    sets: int | None = None
    reps: int | None = None
    rest_seconds: int | None = None
    notes: list[str] = Field(default_factory=list)


class DailyTaskResourceResponse(BaseModel):
    title: str
    resource_type: str
    note: str | None = None


class GeneratedDailyTask(BaseModel):
    title: str
    objective: str | None = None
    description: str | None = None
    instructions: str | None = None
    why_today: str | None = None
    success_criteria: str | None = None
    estimated_minutes: int | None = None

    detail_level: int = 1
    bucket: str = "must"
    priority: str = "medium"

    is_required: bool = True
    proof_required: bool = False
    recommended_proof_type: str | None = None
    proof_prompt: str | None = None

    task_type: str | None = None
    difficulty: str | None = None

    tips: list[str] = Field(default_factory=list)
    technique_cues: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    steps: list[DailyTaskStepResponse] = Field(default_factory=list)
    resources: list[DailyTaskResourceResponse] = Field(default_factory=list)


class GeneratedDailyPlan(BaseModel):
    day_number: int
    focus: str
    summary: str | None = None
    headline: str | None = None
    focus_message: str | None = None
    main_task_title: str | None = None
    total_estimated_minutes: int | None = None
    planned_date: date | None = None
    tasks: list[GeneratedDailyTask] = Field(default_factory=list)


class DailyTaskResponse(BaseModel):
    id: str
    daily_plan_id: str
    goal_id: str

    title: str
    objective: str | None = None
    description: str | None = None
    instructions: str | None = None
    why_today: str | None = None
    success_criteria: str | None = None
    estimated_minutes: int | None = None

    detail_level: int = 1
    bucket: str = "must"
    priority: str = "medium"

    order_index: int
    is_required: bool
    proof_required: bool
    recommended_proof_type: str | None = None
    proof_prompt: str | None = None

    task_type: str | None = None
    difficulty: str | None = None

    tips: list[str] = Field(default_factory=list)
    technique_cues: list[str] = Field(default_factory=list)
    common_mistakes: list[str] = Field(default_factory=list)
    steps: list[DailyTaskStepResponse] = Field(default_factory=list)
    resources: list[DailyTaskResourceResponse] = Field(default_factory=list)

    status: DailyTaskStatus
    completed_at: datetime | None = None
    created_at: datetime


class DailyPlanResponse(BaseModel):
    id: str
    goal_id: str
    day_number: int
    planned_date: date | None = None

    focus: str
    summary: str | None = None
    headline: str | None = None
    focus_message: str | None = None
    main_task_title: str | None = None
    total_estimated_minutes: int | None = None

    status: DailyPlanStatus
    tasks: list[DailyTaskResponse] = Field(default_factory=list)
    created_at: datetime


class TodayPlanResponse(BaseModel):
    date: date
    daily_plan: DailyPlanResponse | None = None


class DailyTaskStatusUpdateRequest(BaseModel):
    status: DailyTaskStatus


class DailyPlanStatusUpdateRequest(BaseModel):
    status: DailyPlanStatus