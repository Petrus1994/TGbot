from fastapi import APIRouter
from app.schemas.goal import (
    CreateGoalRequest,
    GoalResponse,
    GoalListItem,
    SetActiveGoalRequest,
    ChatContextResponse,
)
from app.services.goal_service import create_goal, list_user_goals, set_active_goal

router = APIRouter(tags=["goals"])


@router.post("/goals", response_model=GoalResponse)
def create_goal_endpoint(payload: CreateGoalRequest):
    return create_goal(payload)


@router.get("/goals/{user_id}", response_model=list[GoalListItem])
def list_user_goals_endpoint(user_id: str):
    return list_user_goals(user_id)


@router.post("/chat-context/active-goal", response_model=ChatContextResponse)
def set_active_goal_endpoint(payload: SetActiveGoalRequest):
    return set_active_goal(payload.user_id, payload.goal_id)