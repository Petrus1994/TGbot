from fastapi import APIRouter, HTTPException, status

from app.schemas.plan import AcceptPlanResponse, GeneratePlanRequest, PlanResponse
from app.services.plan_service import accept_plan, generate_plan, get_current_plan

router = APIRouter(tags=["plans"])


@router.post(
    "/goals/{goal_id}/plan/generate",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_plan_endpoint(goal_id: str, payload: GeneratePlanRequest):
    try:
        return generate_plan(goal_id=goal_id, regenerate=payload.regenerate)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/goals/{goal_id}/plan/current",
    response_model=PlanResponse,
)
def get_current_plan_endpoint(goal_id: str):
    plan = get_current_plan(goal_id=goal_id)

    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found for this goal.",
        )

    return plan


@router.post(
    "/goals/{goal_id}/plan/accept",
    response_model=AcceptPlanResponse,
)
def accept_plan_endpoint(goal_id: str):
    try:
        return accept_plan(goal_id=goal_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e