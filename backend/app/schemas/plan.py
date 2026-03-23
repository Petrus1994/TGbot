from datetime import datetime
from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str | None = None
    order: int = Field(..., ge=1)


class PlanContent(BaseModel):
    duration_weeks: int = Field(..., ge=1)
    milestones: list[str]
    steps: list[PlanStep]


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