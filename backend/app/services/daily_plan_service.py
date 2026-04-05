from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text

from app.db import engine
from app.models.daily_plan import DailyPlanStatus
from app.models.daily_task import DailyTaskStatus
from app.schemas.daily_plan import (
    DailyPlanResponse,
    DailyTaskResourceResponse,
    DailyTaskResponse,
    DailyTaskStepResponse,
    GeneratedDailyPlan,
)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    return None


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return []


def _parse_task_steps(value: Any) -> list[DailyTaskStepResponse]:
    raw_steps = _safe_list(value)
    parsed_steps: list[DailyTaskStepResponse] = []

    for item in raw_steps:
        if not isinstance(item, dict):
            continue

        parsed_steps.append(
            DailyTaskStepResponse(
                order=int(item.get("order") or 1),
                title=str(item.get("title") or ""),
                instruction=str(item.get("instruction") or ""),
                duration_minutes=item.get("duration_minutes"),
                sets=item.get("sets"),
                reps=item.get("reps"),
                rest_seconds=item.get("rest_seconds"),
                notes=[
                    str(note)
                    for note in _safe_list(item.get("notes"))
                    if str(note).strip()
                ],
            )
        )

    return parsed_steps


def _parse_task_resources(value: Any) -> list[DailyTaskResourceResponse]:
    raw_resources = _safe_list(value)
    parsed_resources: list[DailyTaskResourceResponse] = []

    for item in raw_resources:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        resource_type = str(item.get("resource_type") or "").strip()

        if not title or not resource_type:
            continue

        parsed_resources.append(
            DailyTaskResourceResponse(
                title=title,
                resource_type=resource_type,
                note=item.get("note"),
            )
        )

    return parsed_resources


def _get_tasks_for_daily_plan(conn, daily_plan_id: str) -> list[DailyTaskResponse]:
    query = text(
        """
        SELECT
            id,
            daily_plan_id,
            goal_id,
            title,
            objective,
            description,
            instructions,
            why_today,
            success_criteria,
            estimated_minutes,
            detail_level,
            bucket,
            priority,
            order_index,
            is_required,
            proof_required,
            recommended_proof_type,
            proof_prompt,
            task_type,
            difficulty,
            tips,
            technique_cues,
            common_mistakes,
            steps,
            resources,
            status,
            completed_at,
            created_at
        FROM daily_tasks
        WHERE daily_plan_id = :daily_plan_id
        ORDER BY order_index ASC, created_at ASC
        """
    )

    rows = conn.execute(query, {"daily_plan_id": daily_plan_id}).mappings().all()

    return [
        DailyTaskResponse(
            id=str(row["id"]),
            daily_plan_id=str(row["daily_plan_id"]),
            goal_id=str(row["goal_id"]),
            title=row["title"],
            objective=row["objective"],
            description=row["description"],
            instructions=row["instructions"],
            why_today=row["why_today"],
            success_criteria=row["success_criteria"],
            estimated_minutes=row["estimated_minutes"],
            detail_level=int(row["detail_level"] or 1),
            bucket=row["bucket"] or "must",
            priority=row["priority"] or "medium",
            order_index=row["order_index"],
            is_required=bool(row["is_required"]),
            proof_required=bool(row["proof_required"]),
            recommended_proof_type=row["recommended_proof_type"],
            proof_prompt=row["proof_prompt"],
            task_type=row["task_type"],
            difficulty=row["difficulty"],
            tips=[
                str(item)
                for item in _safe_list(row["tips"])
                if str(item).strip()
            ],
            technique_cues=[
                str(item)
                for item in _safe_list(row["technique_cues"])
                if str(item).strip()
            ],
            common_mistakes=[
                str(item)
                for item in _safe_list(row["common_mistakes"])
                if str(item).strip()
            ],
            steps=_parse_task_steps(row["steps"]),
            resources=_parse_task_resources(row["resources"]),
            status=DailyTaskStatus(row["status"]),
            completed_at=row["completed_at"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def _build_daily_plan_response(conn, row) -> DailyPlanResponse:
    tasks = _get_tasks_for_daily_plan(conn, str(row["id"]))

    return DailyPlanResponse(
        id=str(row["id"]),
        goal_id=str(row["goal_id"]),
        day_number=row["day_number"] or 1,
        planned_date=_parse_date(row["planned_date"]),
        focus=row["focus"],
        summary=row["summary"],
        headline=row["headline"],
        focus_message=row["focus_message"],
        main_task_title=row["main_task_title"],
        total_estimated_minutes=row["total_estimated_minutes"],
        status=DailyPlanStatus(row["status"]),
        tasks=tasks,
        created_at=row["created_at"],
    )


def create_daily_plans_for_goal(
    goal_id: str,
    generated_days: list[GeneratedDailyPlan],
) -> list[DailyPlanResponse]:
    if not generated_days:
        return []

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_tasks WHERE goal_id = :goal_id"),
            {"goal_id": goal_id},
        )
        conn.execute(
            text("DELETE FROM daily_plans WHERE goal_id = :goal_id"),
            {"goal_id": goal_id},
        )

        insert_daily_plan_query = text(
            """
            INSERT INTO daily_plans (
                goal_id,
                day_number,
                planned_date,
                focus,
                summary,
                headline,
                focus_message,
                main_task_title,
                total_estimated_minutes,
                status
            )
            VALUES (
                :goal_id,
                :day_number,
                :planned_date,
                :focus,
                :summary,
                :headline,
                :focus_message,
                :main_task_title,
                :total_estimated_minutes,
                :status
            )
            RETURNING
                id,
                goal_id,
                day_number,
                planned_date,
                focus,
                summary,
                headline,
                focus_message,
                main_task_title,
                total_estimated_minutes,
                status,
                created_at
            """
        )

        insert_daily_task_query = text(
            """
            INSERT INTO daily_tasks (
                daily_plan_id,
                goal_id,
                title,
                objective,
                description,
                instructions,
                why_today,
                success_criteria,
                estimated_minutes,
                detail_level,
                bucket,
                priority,
                order_index,
                is_required,
                proof_required,
                recommended_proof_type,
                proof_prompt,
                task_type,
                difficulty,
                tips,
                technique_cues,
                common_mistakes,
                steps,
                resources,
                status
            )
            VALUES (
                :daily_plan_id,
                :goal_id,
                :title,
                :objective,
                :description,
                :instructions,
                :why_today,
                :success_criteria,
                :estimated_minutes,
                :detail_level,
                :bucket,
                :priority,
                :order_index,
                :is_required,
                :proof_required,
                :recommended_proof_type,
                :proof_prompt,
                :task_type,
                :difficulty,
                CAST(:tips AS JSONB),
                CAST(:technique_cues AS JSONB),
                CAST(:common_mistakes AS JSONB),
                CAST(:steps AS JSONB),
                CAST(:resources AS JSONB),
                :status
            )
            """
        )

        for day in generated_days:
            parsed_planned_date = _parse_date(day.planned_date)
            if not parsed_planned_date:
                parsed_planned_date = date.today()

            total_estimated_minutes = day.total_estimated_minutes
            if total_estimated_minutes is None:
                total_estimated_minutes = sum(
                    task.estimated_minutes or 0 for task in day.tasks
                ) or None

            daily_plan_row = conn.execute(
                insert_daily_plan_query,
                {
                    "goal_id": goal_id,
                    "day_number": day.day_number,
                    "planned_date": parsed_planned_date,
                    "focus": day.focus,
                    "summary": day.summary,
                    "headline": day.headline,
                    "focus_message": day.focus_message,
                    "main_task_title": day.main_task_title,
                    "total_estimated_minutes": total_estimated_minutes,
                    "status": DailyPlanStatus.pending.value,
                },
            ).mappings().one()

            daily_plan_id = str(daily_plan_row["id"])

            for index, task in enumerate(day.tasks, start=1):
                conn.execute(
                    insert_daily_task_query,
                    {
                        "daily_plan_id": daily_plan_id,
                        "goal_id": goal_id,
                        "title": task.title,
                        "objective": task.objective,
                        "description": task.description,
                        "instructions": task.instructions,
                        "why_today": task.why_today,
                        "success_criteria": task.success_criteria,
                        "estimated_minutes": task.estimated_minutes,
                        "detail_level": task.detail_level,
                        "bucket": task.bucket,
                        "priority": task.priority,
                        "order_index": index,
                        "is_required": task.is_required,
                        "proof_required": task.proof_required,
                        "recommended_proof_type": task.recommended_proof_type,
                        "proof_prompt": task.proof_prompt,
                        "task_type": task.task_type,
                        "difficulty": task.difficulty,
                        "tips": __import__("json").dumps(task.tips, ensure_ascii=False),
                        "technique_cues": __import__("json").dumps(
                            task.technique_cues,
                            ensure_ascii=False,
                        ),
                        "common_mistakes": __import__("json").dumps(
                            task.common_mistakes,
                            ensure_ascii=False,
                        ),
                        "steps": __import__("json").dumps(
                            [step.model_dump() for step in task.steps],
                            ensure_ascii=False,
                        ),
                        "resources": __import__("json").dumps(
                            [resource.model_dump() for resource in task.resources],
                            ensure_ascii=False,
                        ),
                        "status": DailyTaskStatus.pending.value,
                    },
                )

        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                ORDER BY day_number ASC
                """
            ),
            {"goal_id": goal_id},
        ).mappings().all()

        return [_build_daily_plan_response(conn, row) for row in rows]


def get_goal_daily_plans(goal_id: str) -> list[DailyPlanResponse]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                ORDER BY day_number ASC
                """
            ),
            {"goal_id": goal_id},
        ).mappings().all()

        return [_build_daily_plan_response(conn, row) for row in rows]


def get_daily_plan_by_day_number(goal_id: str, day_number: int) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                  AND day_number = :day_number
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "day_number": day_number,
            },
        ).mappings().first()

        if not row:
            return None

        return _build_daily_plan_response(conn, row)


def get_today_plan(goal_id: str, today_date: date | None = None) -> DailyPlanResponse | None:
    today_date = today_date or date.today()

    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                  AND planned_date <= :today_date
                ORDER BY day_number ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "today_date": today_date,
            },
        ).mappings().first()

        if row:
            return _build_daily_plan_response(conn, row)

        fallback_row = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                  AND status IN ('pending', 'in_progress')
                ORDER BY day_number ASC
                LIMIT 1
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not fallback_row:
            return None

        return _build_daily_plan_response(conn, fallback_row)


def recalculate_daily_plan_status(daily_plan_id: str) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        stats_row = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) AS total_tasks,
                    COUNT(*) FILTER (WHERE status = 'done') AS done_tasks,
                    COUNT(*) FILTER (WHERE status = 'skipped') AS skipped_tasks
                FROM daily_tasks
                WHERE daily_plan_id = :daily_plan_id
                """
            ),
            {"daily_plan_id": daily_plan_id},
        ).mappings().one()

        total_tasks = int(stats_row["total_tasks"])
        done_tasks = int(stats_row["done_tasks"])
        skipped_tasks = int(stats_row["skipped_tasks"])

        if total_tasks == 0:
            new_status = DailyPlanStatus.pending.value
        elif done_tasks == total_tasks:
            new_status = DailyPlanStatus.done.value
        elif skipped_tasks == total_tasks:
            new_status = DailyPlanStatus.skipped.value
        elif done_tasks > 0 or skipped_tasks > 0:
            new_status = DailyPlanStatus.in_progress.value
        else:
            new_status = DailyPlanStatus.pending.value

        conn.execute(
            text(
                """
                UPDATE daily_plans
                SET status = :status,
                    updated_at = NOW()
                WHERE id = :daily_plan_id
                """
            ),
            {
                "daily_plan_id": daily_plan_id,
                "status": new_status,
            },
        )

        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": daily_plan_id},
        ).mappings().first()

        if not row:
            return None

        return _build_daily_plan_response(conn, row)


def update_daily_task_status(task_id: str, status: DailyTaskStatus) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        task_row = conn.execute(
            text(
                """
                SELECT id, daily_plan_id
                FROM daily_tasks
                WHERE id = :task_id
                LIMIT 1
                """
            ),
            {"task_id": task_id},
        ).mappings().first()

        if not task_row:
            return None

        completed_at = datetime.now(timezone.utc) if status == DailyTaskStatus.done else None

        conn.execute(
            text(
                """
                UPDATE daily_tasks
                SET status = :status,
                    completed_at = :completed_at,
                    updated_at = NOW()
                WHERE id = :task_id
                """
            ),
            {
                "task_id": task_id,
                "status": status.value,
                "completed_at": completed_at,
            },
        )

    return recalculate_daily_plan_status(str(task_row["daily_plan_id"]))


def update_daily_plan_status(
    daily_plan_id: str,
    status: DailyPlanStatus,
) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE daily_plans
                SET status = :status,
                    updated_at = NOW()
                WHERE id = :daily_plan_id
                """
            ),
            {
                "daily_plan_id": daily_plan_id,
                "status": status.value,
            },
        )

        if status in {DailyPlanStatus.done, DailyPlanStatus.skipped}:
            task_status = (
                DailyTaskStatus.done.value
                if status == DailyPlanStatus.done
                else DailyTaskStatus.skipped.value
            )
            completed_at = datetime.now(timezone.utc) if status == DailyPlanStatus.done else None

            conn.execute(
                text(
                    """
                    UPDATE daily_tasks
                    SET status = :task_status,
                        completed_at = :completed_at,
                        updated_at = NOW()
                    WHERE daily_plan_id = :daily_plan_id
                      AND status = 'pending'
                    """
                ),
                {
                    "daily_plan_id": daily_plan_id,
                    "task_status": task_status,
                    "completed_at": completed_at,
                },
            )

        row = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    day_number,
                    planned_date,
                    focus,
                    summary,
                    headline,
                    focus_message,
                    main_task_title,
                    total_estimated_minutes,
                    status,
                    created_at
                FROM daily_plans
                WHERE id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": daily_plan_id},
        ).mappings().first()

        if not row:
            return None

        return _build_daily_plan_response(conn, row)