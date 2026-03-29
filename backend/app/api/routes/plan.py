from fastapi import APIRouter, HTTPException, status

from app.core.exceptions import (
    AIPlanGenerationError,
    GoalNotFoundError,
    ProfilingIncompleteError,
)
from app.schemas.plan import AcceptPlanResponse, GeneratePlanRequest, PlanResponse
from app.services.plan_generation_service import PlanGenerationService
from app.services.plan_service import accept_plan, generate_plan as generate_stub_plan, get_current_plan

router = APIRouter(tags=["plans"])

plan_generation_service = PlanGenerationService()


@router.post(
    "/goals/{goal_id}/plan/generate",
    response_model=PlanResponse,
    status_code=status.HTTP_201_CREATED,
)
async def generate_plan_endpoint(goal_id: str, payload: GeneratePlanRequest):
    try:
        return await plan_generation_service.generate_plan(
            goal_id=goal_id,
            regenerate=payload.regenerate,
        )
    except GoalNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e) or "goal_not_found",
        ) from e
    except ProfilingIncompleteError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e) or "profiling_incomplete",
        ) from e
    except AIPlanGenerationError:
        try:
            return generate_stub_plan(goal_id=goal_id, regenerate=payload.regenerate)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"plan_generation_failed: {str(e)}",
            ) from e
    except Exception:
        try:
            return generate_stub_plan(goal_id=goal_id, regenerate=payload.regenerate)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"plan_generation_failed: {str(e)}",
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