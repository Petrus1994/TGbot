from datetime import date, datetime
from pydantic import BaseModel, Field

from app.models.daily_plan import DailyPlanStatus
from app.models.daily_task import DailyTaskStatus


class GeneratedDailyTask(BaseModel):
    title: str
    description: str | None = None
    instructions: str | None = None
    estimated_minutes: int | None = None
    is_required: bool = True
    proof_required: bool = False


class GeneratedDailyPlan(BaseModel):
    day_number: int
    focus: str
    summary: str | None = None
    planned_date: date | None = None
    tasks: list[GeneratedDailyTask] = Field(default_factory=list)


class DailyTaskResponse(BaseModel):
    id: str
    daily_plan_id: str
    goal_id: str
    title: str
    description: str | None = None
    instructions: str | None = None
    estimated_minutes: int | None = None
    order_index: int
    is_required: bool
    proof_required: bool
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