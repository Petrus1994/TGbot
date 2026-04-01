from pydantic import BaseModel, Field


class AIPlanStepV2(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AIPlanTaskV2(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    cadence_type: str = Field(min_length=1)
    cadence_config: dict = Field(default_factory=dict)
    proof_type: str = Field(min_length=1)
    proof_required: bool = True


class AIPlanResponseV2(BaseModel):
    summary: str = Field(min_length=1)
    duration_weeks: int = Field(ge=1)
    steps: list[AIPlanStepV2] = Field(min_length=4, max_length=6)
    tasks: list[AIPlanTaskV2] = Field(min_length=3, max_length=7)