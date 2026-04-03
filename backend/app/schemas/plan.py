from datetime import date, datetime
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str | None = None
    order: int = Field(..., ge=1)


class DailyTaskContent(BaseModel):
    title: str
    description: str | None = None
    instructions: str | None = None
    estimated_minutes: int | None = Field(default=None, ge=1)
    is_required: bool = True
    proof_required: bool = False


class DailyPlanContent(BaseModel):
    day_number: int = Field(..., ge=1)
    focus: str
    summary: str | None = None
    planned_date: date | None = None
    tasks: list[DailyTaskContent] = Field(default_factory=list)


class PlanContent(BaseModel):
    duration_weeks: int = Field(..., ge=1)
    milestones: list[str]
    steps: list[PlanStep]
    days: list[DailyPlanContent] = Field(default_factory=list)


class GeneratePlanRequest(BaseModel):
    regenerate: bool = False


class PlanResponse(BaseModel):
    id: str
    goal_id: str
    status: str
    title: str
    summary: str | None = None
    content: PlanContent
    accepted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AcceptPlanResponse(BaseModel):
    success: bool
    plan: PlanResponse