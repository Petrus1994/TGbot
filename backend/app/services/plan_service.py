from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.plan import GoalPlan, PlanStatus
from app.repositories.plan_repository import PlanRepository
from app.schemas.plan import AcceptPlanResponse, PlanResponse


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


def _serialize_plan_content(content: dict) -> str:
    try:
        return json.dumps(content, ensure_ascii=False)
    except Exception as e:
        print(f"❌ JSON SERIALIZATION ERROR: {repr(e)}")
        return "{}"


def _deserialize_plan_content(content_json: str) -> dict:
    try:
        return json.loads(content_json)
    except Exception as e:
        print(f"❌ JSON DESERIALIZATION ERROR: {repr(e)}")
        return {}


def _to_plan_response(plan: GoalPlan) -> PlanResponse:
    return PlanResponse(
        id=str(plan.id),
        goal_id=str(plan.goal_id),
        status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        title=plan.title,
        summary=plan.summary,
        content=_deserialize_plan_content(plan.content_json),
        accepted_at=plan.accepted_at,
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def save_generated_plan(
    *,
    goal_id: str,
    title: str,
    summary: str,
    content: dict,
    status: str = "draft",
) -> PlanResponse:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)

        plan = repo.create(
            goal_id=UUID(goal_id),
            title=title,
            summary=summary,
            content_json=_serialize_plan_content(content),
            status=PlanStatus(status),
        )

        return _to_plan_response(plan)

    except Exception as e:
        print(f"❌ SAVE GENERATED PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()


def generate_plan(goal_id: str, regenerate: bool = False) -> PlanResponse:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)

        existing = repo.get_latest_by_goal_id(UUID(goal_id))
        if existing and not regenerate:
            return _to_plan_response(existing)

        content = _build_stub_plan(goal_id)

        plan = repo.create(
            goal_id=UUID(goal_id),
            title="Personal goal execution plan",
            summary="Stub plan generated from current goal and profiling data.",
            content_json=_serialize_plan_content(content),
            status=PlanStatus.draft,
        )

        return _to_plan_response(plan)

    except Exception as e:
        print(f"❌ GENERATE PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()


def get_current_plan(goal_id: str) -> PlanResponse | None:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)
        plan = repo.get_latest_by_goal_id(UUID(goal_id))

        if not plan:
            return None

        return _to_plan_response(plan)

    except Exception as e:
        print(f"❌ GET CURRENT PLAN ERROR: {repr(e)}")
        return None

    finally:
        db.close()


def accept_plan(goal_id: str) -> AcceptPlanResponse:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)

        plan = repo.get_latest_by_goal_id(UUID(goal_id))
        if not plan:
            raise ValueError("No generated plan found for this goal.")

        now = datetime.now(timezone.utc)
        plan.status = PlanStatus.accepted
        plan.accepted_at = now

        saved = repo.save(plan)

        return AcceptPlanResponse(
            success=True,
            plan=_to_plan_response(saved),
        )

    except Exception as e:
        print(f"❌ ACCEPT PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()