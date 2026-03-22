from pydantic import BaseModel
from datetime import date


class CreateGoalRequest(BaseModel):
    user_id: str
    title: str
    description: str | None = None
    category: str | None = None
    target_date: date | None = None
    priority: int | None = None


class GoalResponse(BaseModel):
    goal_id: str
    user_id: str
    title: str
    description: str | None = None
    category: str | None = None
    target_date: date | None = None
    status: str
    priority: int | None = None


class SetActiveGoalRequest(BaseModel):
    user_id: str
    goal_id: str


class ChatContextResponse(BaseModel):
    user_id: str
    active_goal_id: str | None = None
    last_selected_goal_id: str | None = None
    state: str | None = None
    substate: str | None = None


class GoalListItem(BaseModel):
    goal_id: str
    title: str
    status: str
    category: str | None = None
    priority: int | None = None
    target_date: date | None = None
