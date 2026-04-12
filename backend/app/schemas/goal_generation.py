from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class GoalGenerationContext(BaseModel):
    goal_id: str
    user_id: str

    goal_title: str
    goal_description: str | None = None

    current_level: str | None = None
    constraints: str | None = None
    resources: str | None = None
    motivation: str | None = None
    coach_style: str | None = None

    goal_outcome: str | None = None
    deadline: str | None = None
    time_budget: str | None = None
    past_attempts: str | None = None
    main_obstacles: str | None = None
    daily_routine: str | None = None
    planning_notes: str | None = None
    plan_confidence: str | None = None

    profiling_summary: dict[str, Any] = Field(default_factory=dict)
    profiling_answers: dict[str, Any] = Field(default_factory=dict)