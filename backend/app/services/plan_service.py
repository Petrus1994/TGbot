from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.plan import AcceptPlanResponse, PlanResponse

_PLAN_STORE: dict[str, dict] = {}


def _build_stub_plan(goal_id: str) -> dict:
    return {
        "duration_weeks": 4,
        "milestones": [
            "Clarify scope and success criteria",
            "Build a consistent weekly routine",
            "Complete first measurable result",
            "Review progress and lock next iteration",
        ],
        "steps": [
            {
                "step_id": f"{goal_id}-step-1",
                "title": "Foundation",
                "description": "Define constraints, available time, and success metrics.",
                "order": 1,
            },
            {
                "step_id": f"{goal_id}-step-2",
                "title": "Execution start",
                "description": "Begin the first active implementation cycle.",
                "order": 2,
            },
            {
                "step_id": f"{goal_id}-step-3",
                "title": "Momentum",
                "description": "Increase consistency and remove friction.",
                "order": 3,
            },
            {
                "step_id": f"{goal_id}-step-4",
                "title": "Review and next step",
                "description": "Evaluate results and prepare the next plan version.",
                "order": 4,
            },
        ],
    }


def generate_plan(goal_id: str, regenerate: bool = False) -> PlanResponse:
    if goal_id in _PLAN_STORE and not regenerate:
        return PlanResponse(**_PLAN_STORE[goal_id])

    now = datetime.now(timezone.utc)
    content = _build_stub_plan(goal_id)

    plan = {
        "id": str(uuid4()),
        "goal_id": goal_id,
        "status": "draft",
        "title": "Personal goal execution plan",
        "summary": "Stub plan generated from current goal and profiling data.",
        "content": content,
        "accepted_at": None,
        "created_at": now,
        "updated_at": now,
    }

    _PLAN_STORE[goal_id] = plan
    return PlanResponse(**plan)


def get_current_plan(goal_id: str) -> PlanResponse | None:
    plan = _PLAN_STORE.get(goal_id)
    if not plan:
        return None
    return PlanResponse(**plan)


def accept_plan(goal_id: str) -> AcceptPlanResponse:
    plan = _PLAN_STORE.get(goal_id)

    if not plan:
        raise ValueError("No generated plan found for this goal.")

    now = datetime.now(timezone.utc)
    plan["status"] = "accepted"
    plan["accepted_at"] = now
    plan["updated_at"] = now

    return AcceptPlanResponse(
        success=True,
        plan=PlanResponse(**plan),
    )