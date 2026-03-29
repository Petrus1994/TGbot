from pydantic import BaseModel, Field


class AIPlanStep(BaseModel):
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)


class AIPlanResponse(BaseModel):
    summary: str = Field(min_length=1)
    steps: list[AIPlanStep]