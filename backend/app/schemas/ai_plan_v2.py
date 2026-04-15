from __future__ import annotations

from pydantic import BaseModel, Field


class AIPlanStepV2(BaseModel):
    title: str
    description: str


class AIPlanTaskV2(BaseModel):
    title: str
    description: str

    cadence_type: str
    cadence_config: dict = Field(default_factory=dict)

    proof_type: str
    proof_required: bool = True
    proof_prompt: str | None = None


class AIPlanResponseV2(BaseModel):
    summary: str
    duration_weeks: int
    steps: list[AIPlanStepV2] = Field(default_factory=list)
    tasks: list[AIPlanTaskV2] = Field(default_factory=list)