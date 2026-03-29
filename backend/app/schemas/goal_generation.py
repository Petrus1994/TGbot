from pydantic import BaseModel


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