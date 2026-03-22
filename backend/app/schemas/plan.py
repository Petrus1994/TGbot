from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PlanStep(BaseModel):
    week: int = Field(..., ge=1)
    title: str
    description: str
    tasks: list[str]


class PlanContent(BaseModel):
    duration_weeks: int = Field(..., ge=1)
    milestones: list[str]
    steps: list[PlanStep]


class GeneratePlanRequest(BaseModel):
    regenerate: bool = False


class PlanResponse(BaseModel):
    id: UUID
    goal_id: UUID
    status: str
    title: str
    summary: str | None
    content: PlanContent
    accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AcceptPlanResponse(BaseModel):
    success: bool = True
    plan: PlanResponse


class ErrorResponse(BaseModel):
    detail: str