import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.schemas.plan import AcceptPlanResponse, PlanContent, PlanResponse

_PLAN_STORE: dict[str, dict] = {}


def _build_stub_plan(goal_id: UUID) -> dict:
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
                "week": 1,
                "title": "Foundation",
                "description": "Define constraints, available time, and success metrics.",
                "tasks": [
                    "Write down the exact target outcome",
                    "List blockers and available resources",
                    "Commit to 3 fixed work sessions this week",
                ],
            },
            {
                "week": 2,
                "title": "Execution start",
                "description": "Begin the first active implementation cycle.",
                "tasks": [
                    "Complete the smallest meaningful deliverable",
                    "Track completion after each session",
                    "Adjust workload if plan is unrealistic",
                ],
            },
            {
                "week": 3,
                "title": "Momentum",
                "description": "Increase consistency and remove friction.",
                "tasks": [
                    "Repeat the core routine at least 3 times",
                    "Remove one recurring blocker",
                    "Document what is already working",
                ],
            },
            {
                "week": 4,
                "title": "Review and next step",
                "description": "Evaluate results and prepare the next plan version.",
                "tasks": [
                    "Assess progress against initial metric",
                    "Keep what worked, discard what did not",
                    "Prepare next 4-week iteration",
                ],
            },
        ],
    }


def generate_plan(goal_id: UUID, regenerate: bool = False) -> PlanResponse:
    goal_id_str = str(goal_id)

    if goal_id_str in _PLAN_STORE and not regenerate:
        return PlanResponse(**_PLAN_STORE[goal_id_str])

    now = datetime.now(timezone.utc)
    content = _build_stub_plan(goal_id)

    plan = {
        "id": uuid4(),
        "goal_id": goal_id,
        "status": "draft",
        "title": "Personal goal execution plan",
        "summary": "Stub plan generated from current goal and profiling data.",
        "content": content,
        "accepted_at": None,
        "created_at": now,
        "updated_at": now,
    }

    _PLAN_STORE[goal_id_str] = plan
    return PlanResponse(**plan)


def get_current_plan(goal_id: UUID) -> PlanResponse | None:
    plan = _PLAN_STORE.get(str(goal_id))
    if not plan:
        return None
    return PlanResponse(**plan)


def accept_plan(goal_id: UUID) -> AcceptPlanResponse:
    goal_id_str = str(goal_id)
    plan = _PLAN_STORE.get(goal_id_str)

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