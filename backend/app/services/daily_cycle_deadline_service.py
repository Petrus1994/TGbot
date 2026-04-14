from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from app.db import engine
from app.services.daily_cycle_service import mark_overdue_cycles


def _serialize_cycle(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "cycle_id": str(row["cycle_id"]),
        "goal_id": str(row["goal_id"]),
        "daily_plan_id": str(row["daily_plan_id"]),
        "cycle_index": int(row["cycle_index"]),
        "status": str(row["status"]),
        "opened_at": row["opened_at"],
        "due_at": row["due_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def run_deadline_check(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)

    missed_cycles = mark_overdue_cycles(now=now)

    return {
        "checked_at": now,
        "missed_cycles_count": len(missed_cycles),
        "missed_cycles": [_serialize_cycle(cycle) for cycle in missed_cycles],
    }


def get_goal_cycle_deadline_state(goal_id: str) -> dict[str, Any]:
    with engine.begin() as conn:
        active_cycle = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at,
                    created_at,
                    updated_at
                FROM daily_plan_cycles
                WHERE goal_id = :goal_id
                  AND status = 'active'
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        latest_cycle = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at,
                    created_at,
                    updated_at
                FROM daily_plan_cycles
                WHERE goal_id = :goal_id
                ORDER BY cycle_index DESC
                LIMIT 1
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        total_cycles_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS total_cycles
                FROM daily_plan_cycles
                WHERE goal_id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().one()

        missed_cycles_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS missed_cycles
                FROM daily_plan_cycles
                WHERE goal_id = :goal_id
                  AND status = 'missed'
                """
            ),
            {"goal_id": goal_id},
        ).mappings().one()

        completed_cycles_row = conn.execute(
            text(
                """
                SELECT COUNT(*) AS completed_cycles
                FROM daily_plan_cycles
                WHERE goal_id = :goal_id
                  AND status = 'completed'
                """
            ),
            {"goal_id": goal_id},
        ).mappings().one()

    return {
        "goal_id": goal_id,
        "has_active_cycle": active_cycle is not None,
        "active_cycle": _serialize_cycle(active_cycle) if active_cycle else None,
        "latest_cycle": _serialize_cycle(latest_cycle) if latest_cycle else None,
        "total_cycles": int(total_cycles_row["total_cycles"] or 0),
        "completed_cycles": int(completed_cycles_row["completed_cycles"] or 0),
        "missed_cycles": int(missed_cycles_row["missed_cycles"] or 0),
    }


def get_overdue_active_cycles(now: datetime | None = None) -> list[dict[str, Any]]:
    now = now or datetime.now(timezone.utc)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT
                    id,
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at,
                    created_at,
                    updated_at
                FROM daily_plan_cycles
                WHERE status = 'active'
                  AND due_at < :now_utc
                ORDER BY due_at ASC
                """
            ),
            {"now_utc": now},
        ).mappings().all()

    serialized: list[dict[str, Any]] = []
    for row in rows:
        serialized.append(
            {
                "cycle_id": str(row["id"]),
                "goal_id": str(row["goal_id"]),
                "daily_plan_id": str(row["daily_plan_id"]),
                "cycle_index": int(row["cycle_index"]),
                "status": str(row["status"]),
                "opened_at": row["opened_at"],
                "due_at": row["due_at"],
                "completed_at": row["completed_at"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
        )

    return serialized