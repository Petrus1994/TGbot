from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import text

from app.db import engine
from app.schemas.daily_plan import (
    DailyPlanResponse,
    DailyTaskResponse,
    GeneratedDailyPlan,
)
from app.models.daily_plan import DailyPlanStatus
from app.models.daily_task import DailyTaskStatus


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


def _get_tasks_for_daily_plan(conn, daily_plan_id: str) -> list[DailyTaskResponse]:
    query = text(
        """
        SELECT
            id,
            daily_plan_id,
            goal_id,
            title,
            description,
            instructions,
            estimated_minutes,
            order_index,
            is_required,
            proof_required,
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
            description=row["description"],
            instructions=row["instructions"],
            estimated_minutes=row["estimated_minutes"],
            order_index=row["order_index"],
            is_required=bool(row["is_required"]),
            proof_required=bool(row["proof_required"]),
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
        day_number=row["day_number"],
        planned_date=_parse_date(row["planned_date"]),
        focus=row["focus"],
        summary=row["summary"],
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
                status
            )
            VALUES (
                :goal_id,
                :day_number,
                :planned_date,
                :focus,
                :summary,
                :status
            )
            RETURNING
                id,
                goal_id,
                day_number,
                planned_date,
                focus,
                summary,
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
                description,
                instructions,
                estimated_minutes,
                order_index,
                is_required,
                proof_required,
                status
            )
            VALUES (
                :daily_plan_id,
                :goal_id,
                :title,
                :description,
                :instructions,
                :estimated_minutes,
                :order_index,
                :is_required,
                :proof_required,
                :status
            )
            """
        )

        for day in generated_days:
            parsed_planned_date = _parse_date(day.planned_date)

            daily_plan_row = conn.execute(
                insert_daily_plan_query,
                {
                    "goal_id": goal_id,
                    "day_number": day.day_number,
                    "planned_date": parsed_planned_date,
                    "focus": day.focus,
                    "summary": day.summary,
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
                        "description": task.description,
                        "instructions": task.instructions,
                        "estimated_minutes": task.estimated_minutes,
                        "order_index": index,
                        "is_required": task.is_required,
                        "proof_required": task.proof_required,
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
                    status,
                    created_at
                FROM daily_plans
                WHERE goal_id = :goal_id
                  AND planned_date = :today_date
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