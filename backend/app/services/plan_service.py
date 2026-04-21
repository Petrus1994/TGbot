from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models.plan import GoalPlan, PlanStatus
from app.repositories.plan_repository import PlanRepository
from app.schemas.daily_plan import GeneratedDailyPlan, GeneratedDailyTask
from app.schemas.plan import AcceptPlanResponse, PlanContent, PlanResponse
from app.services.daily_cycle_service import assign_first_cycle_for_goal
from app.services.daily_plan_service import (
    create_daily_plans_for_goal,
    enrich_next_actionable_daily_plan_if_needed,
)


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
        "days": [
            {
                "day_number": 1,
                "focus": "Foundation and setup",
                "summary": "Prepare the base environment and define the first execution rhythm.",
                "tasks": [
                    {
                        "title": "Write down exact goal outcome",
                        "description": "Make the target specific and measurable.",
                        "instructions": "Write 1-2 sentences describing the exact result you want and how you will know it is achieved.",
                        "estimated_minutes": 10,
                        "is_required": True,
                        "proof_required": False,
                    },
                    {
                        "title": "Block time for goal work",
                        "description": "Reserve time in your day for execution.",
                        "instructions": "Choose a concrete 30-60 minute slot today or tomorrow and put it in your calendar.",
                        "estimated_minutes": 10,
                        "is_required": True,
                        "proof_required": False,
                    },
                    {
                        "title": "Complete the first small action",
                        "description": "Start with a low-friction win.",
                        "instructions": "Do the easiest useful first action related to your goal for at least 20 minutes.",
                        "estimated_minutes": 20,
                        "is_required": True,
                        "proof_required": False,
                    },
                ],
            },
            {
                "day_number": 2,
                "focus": "Execution start",
                "summary": "Begin consistent execution with a clear small workload.",
                "tasks": [
                    {
                        "title": "Do one focused work session",
                        "description": "Deep work on the goal without distractions.",
                        "instructions": "Work on the goal for 25-45 minutes with notifications off and no multitasking.",
                        "estimated_minutes": 30,
                        "is_required": True,
                        "proof_required": False,
                    },
                    {
                        "title": "Log friction points",
                        "description": "Notice what makes execution harder.",
                        "instructions": "Write down 1-3 things that slowed you down today.",
                        "estimated_minutes": 5,
                        "is_required": True,
                        "proof_required": False,
                    },
                ],
            },
            {
                "day_number": 3,
                "focus": "Consistency",
                "summary": "Repeat the routine and reduce resistance.",
                "tasks": [
                    {
                        "title": "Repeat your scheduled goal session",
                        "description": "Keep the streak going.",
                        "instructions": "Do another focused session at the same or similar time as planned.",
                        "estimated_minutes": 30,
                        "is_required": True,
                        "proof_required": False,
                    },
                    {
                        "title": "Remove one source of friction",
                        "description": "Make tomorrow easier than today.",
                        "instructions": "Prepare tools, notes, clothes, files, or workspace in advance for the next session.",
                        "estimated_minutes": 10,
                        "is_required": True,
                        "proof_required": False,
                    },
                ],
            },
            {
                "day_number": 4,
                "focus": "Review and next step",
                "summary": "Measure progress and lock the next iteration.",
                "tasks": [
                    {
                        "title": "Review what was completed",
                        "description": "Assess the first cycle honestly.",
                        "instructions": "List what you completed this week and what remains unfinished.",
                        "estimated_minutes": 10,
                        "is_required": True,
                        "proof_required": False,
                    },
                    {
                        "title": "Define the next concrete milestone",
                        "description": "Turn momentum into the next action.",
                        "instructions": "Write the next milestone and the first task for it.",
                        "estimated_minutes": 10,
                        "is_required": True,
                        "proof_required": False,
                    },
                ],
            },
        ],
    }


def _serialize_plan_content(content: dict) -> str:
    try:
        return json.dumps(content, ensure_ascii=False, default=str)
    except Exception as e:
        print(f"❌ JSON SERIALIZATION ERROR: {repr(e)}")
        return "{}"


def _deserialize_plan_content(content_json: str) -> dict:
    try:
        return json.loads(content_json)
    except Exception as e:
        print(f"❌ JSON DESERIALIZATION ERROR: {repr(e)}")
        return {}


def _content_dict_to_generated_days(content: dict) -> list[GeneratedDailyPlan]:
    raw_days = content.get("days") or []
    generated_days: list[GeneratedDailyPlan] = []

    for raw_day in raw_days:
        tasks = [
            GeneratedDailyTask(
                title=task["title"],
                objective=task.get("objective"),
                description=task.get("description"),
                instructions=task.get("instructions"),
                why_today=task.get("why_today"),
                success_criteria=task.get("success_criteria"),
                estimated_minutes=task.get("estimated_minutes"),
                detail_level=task.get("detail_level", 1),
                bucket=task.get("bucket", "must"),
                priority=task.get("priority", "medium"),
                is_required=task.get("is_required", True),
                proof_required=task.get("proof_required", False),
                recommended_proof_type=task.get("recommended_proof_type"),
                proof_prompt=task.get("proof_prompt"),
                task_type=task.get("task_type"),
                difficulty=task.get("difficulty"),
                tips=task.get("tips") or [],
                technique_cues=task.get("technique_cues") or [],
                common_mistakes=task.get("common_mistakes") or [],
                steps=task.get("steps") or [],
                resources=task.get("resources") or [],
            )
            for task in raw_day.get("tasks", [])
        ]

        generated_days.append(
            GeneratedDailyPlan(
                day_number=raw_day["day_number"],
                focus=raw_day["focus"],
                summary=raw_day.get("summary"),
                headline=raw_day.get("headline"),
                focus_message=raw_day.get("focus_message"),
                main_task_title=raw_day.get("main_task_title"),
                total_estimated_minutes=raw_day.get("total_estimated_minutes"),
                planned_date=raw_day.get("planned_date"),
                tasks=tasks,
            )
        )

    return generated_days


def _sync_daily_plans(goal_id: str, content: dict) -> None:
    generated_days = _content_dict_to_generated_days(content)
    create_daily_plans_for_goal(goal_id, generated_days)


def _to_plan_response(plan: GoalPlan) -> PlanResponse:
    content_dict = _deserialize_plan_content(plan.content_json)
    content = PlanContent.model_validate(content_dict)

    return PlanResponse(
        id=str(plan.id),
        goal_id=str(plan.goal_id),
        status=plan.status.value if hasattr(plan.status, "value") else str(plan.status),
        title=plan.title,
        summary=plan.summary,
        content=content,
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

        validated_content = PlanContent.model_validate(content)
        normalized_content = validated_content.model_dump(mode="json")

        if status == PlanStatus.draft.value:
            repo.deactivate_old_drafts(UUID(goal_id))

        latest_plan = repo.get_latest_by_goal_id(UUID(goal_id))
        next_version = (latest_plan.version + 1) if latest_plan else 1

        plan = repo.create(
            goal_id=UUID(goal_id),
            title=title,
            summary=summary,
            content_json=_serialize_plan_content(normalized_content),
            status=PlanStatus(status),
        )

        if plan.version != next_version:
            plan.version = next_version
            plan = repo.save(plan)

        return _to_plan_response(plan)

    except Exception as e:
        db.rollback()
        print(f"❌ SAVE GENERATED PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()


def generate_plan(goal_id: str, regenerate: bool = False) -> PlanResponse:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)

        existing = repo.get_active_plan_by_goal_id(UUID(goal_id))
        if existing and not regenerate:
            return _to_plan_response(existing)

        if regenerate:
            repo.deactivate_old_drafts(UUID(goal_id))

        latest_plan = repo.get_latest_by_goal_id(UUID(goal_id))
        next_version = (latest_plan.version + 1) if latest_plan else 1

        content = _build_stub_plan(goal_id)
        validated_content = PlanContent.model_validate(content)
        normalized_content = validated_content.model_dump(mode="json")

        plan = repo.create(
            goal_id=UUID(goal_id),
            title="Personal goal execution plan",
            summary="Stub plan generated from current goal and profiling data.",
            content_json=_serialize_plan_content(normalized_content),
            status=PlanStatus.draft,
        )

        if plan.version != next_version:
            plan.version = next_version
            plan = repo.save(plan)

        return _to_plan_response(plan)

    except Exception as e:
        db.rollback()
        print(f"❌ GENERATE PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()


def get_current_plan(goal_id: str) -> PlanResponse | None:
    db: Session = SessionLocal()
    try:
        repo = PlanRepository(db)
        plan = repo.get_active_plan_by_goal_id(UUID(goal_id))

        if not plan:
            return None

        return _to_plan_response(plan)

    except Exception as e:
        print(f"❌ GET CURRENT PLAN ERROR: {repr(e)}")
        return None

    finally:
        db.close()


async def accept_plan(goal_id: str) -> AcceptPlanResponse:
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
        content = _deserialize_plan_content(saved.content_json)

        _sync_daily_plans(goal_id, content)
        assign_first_cycle_for_goal(goal_id)

        try:
            asyncio.create_task(
                enrich_next_actionable_daily_plan_if_needed(goal_id)
            )
        except Exception as e:
            print(f"⚠️ ACCEPT PLAN PREPARE DAY FAILED: {e}")

        return AcceptPlanResponse(
            success=True,
            plan=_to_plan_response(saved),
        )

    except Exception as e:
        db.rollback()
        print(f"❌ ACCEPT PLAN ERROR: {repr(e)}")
        raise

    finally:
        db.close()