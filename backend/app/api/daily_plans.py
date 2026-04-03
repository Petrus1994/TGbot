from datetime import date

from fastapi import APIRouter, HTTPException, status

from app.schemas.daily_plan import (
    DailyPlanResponse,
    DailyPlanStatusUpdateRequest,
    DailyTaskStatusUpdateRequest,
    TodayPlanResponse,
)
from app.services.daily_plan_service import (
    get_daily_plan_by_day_number,
    get_goal_daily_plans,
    get_today_plan,
    update_daily_plan_status,
    update_daily_task_status,
)

router = APIRouter(tags=["daily_plans"])


@router.get(
    "/goals/{goal_id}/daily-plans",
    response_model=list[DailyPlanResponse],
)
def list_goal_daily_plans(goal_id: str):
    return get_goal_daily_plans(goal_id)


@router.get(
    "/goals/{goal_id}/daily-plans/today",
    response_model=TodayPlanResponse,
)
def get_goal_today_plan(goal_id: str):
    daily_plan = get_today_plan(goal_id)

    return TodayPlanResponse(
        date=date.today(),
        daily_plan=daily_plan,
    )


@router.get(
    "/goals/{goal_id}/daily-plans/{day_number}",
    response_model=DailyPlanResponse,
)
def get_goal_daily_plan_by_day(goal_id: str, day_number: int):
    daily_plan = get_daily_plan_by_day_number(goal_id, day_number)

    if not daily_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily plan not found",
        )

    return daily_plan


@router.post(
    "/daily-tasks/{task_id}/status",
    response_model=DailyPlanResponse,
)
def set_daily_task_status(task_id: str, payload: DailyTaskStatusUpdateRequest):
    daily_plan = update_daily_task_status(task_id, payload.status)

    if not daily_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily task not found",
        )

    return daily_plan


@router.post(
    "/daily-plans/{daily_plan_id}/status",
    response_model=DailyPlanResponse,
)
def set_daily_plan_status(
    daily_plan_id: str,
    payload: DailyPlanStatusUpdateRequest,
):
    daily_plan = update_daily_plan_status(daily_plan_id, payload.status)

    if not daily_plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Daily plan not found",
        )

    return daily_plan