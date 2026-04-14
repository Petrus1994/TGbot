from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import re
from typing import Any

from sqlalchemy import text

from app.db import engine


ACTIVE_CYCLE_STATUS = "active"
COMPLETED_CYCLE_STATUS = "completed"
MISSED_CYCLE_STATUS = "missed"
CANCELLED_CYCLE_STATUS = "cancelled"


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except Exception:
            return None
    return None


def _end_of_day_utc(target_date: date) -> datetime:
    return datetime.combine(
        target_date,
        time(hour=23, minute=59, second=59, microsecond=0),
        tzinfo=timezone.utc,
    )


def _normalize_weekday_value(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None

    if isinstance(value, int):
        if 1 <= value <= 7:
            return value
        if 0 <= value <= 6:
            return 7 if value == 0 else value
        return None

    raw = str(value).strip().lower()
    if not raw:
        return None

    mapping = {
        "monday": 1,
        "mon": 1,
        "понедельник": 1,
        "пн": 1,
        "tuesday": 2,
        "tue": 2,
        "tues": 2,
        "вторник": 2,
        "вт": 2,
        "wednesday": 3,
        "wed": 3,
        "среда": 3,
        "ср": 3,
        "thursday": 4,
        "thu": 4,
        "thur": 4,
        "thurs": 4,
        "четверг": 4,
        "чт": 4,
        "friday": 5,
        "fri": 5,
        "пятница": 5,
        "пт": 5,
        "saturday": 6,
        "sat": 6,
        "суббота": 6,
        "сб": 6,
        "sunday": 7,
        "sun": 7,
        "воскресенье": 7,
        "вс": 7,
    }

    if raw in mapping:
        return mapping[raw]

    parts = [part.strip() for part in re.split(r"[,;/|]+", raw) if part.strip()]
    if len(parts) > 1:
        return None

    digits = re.findall(r"\d+", raw)
    if digits:
        num = int(digits[0])
        if 1 <= num <= 7:
            return num
        if 0 <= num <= 6:
            return 7 if num == 0 else num

    return None


def _extract_weekdays(value: Any) -> set[int]:
    if value is None:
        return set()

    if isinstance(value, list):
        result: set[int] = set()
        for item in value:
            result.update(_extract_weekdays(item))
        return result

    if isinstance(value, dict):
        result: set[int] = set()
        for nested in value.values():
            result.update(_extract_weekdays(nested))
        return result

    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"[,;/|]+", value) if part.strip()]
        if len(parts) > 1:
            result: set[int] = set()
            for part in parts:
                normalized = _normalize_weekday_value(part)
                if normalized is not None:
                    result.add(normalized)
            return result

    normalized = _normalize_weekday_value(value)
    return {normalized} if normalized is not None else set()


def _map_cycle_row(row) -> dict[str, Any]:
    return {
        "cycle_id": str(row["id"]),
        "goal_id": str(row["goal_id"]),
        "daily_plan_id": str(row["daily_plan_id"]),
        "cycle_index": int(row["cycle_index"]),
        "status": row["status"],
        "opened_at": row["opened_at"],
        "due_at": row["due_at"],
        "completed_at": row["completed_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _get_daily_plan_row(conn, daily_plan_id: str):
    return conn.execute(
        text(
            """
            SELECT
                id,
                goal_id,
                day_number,
                planned_date,
                status,
                created_at
            FROM daily_plans
            WHERE id = :daily_plan_id
            LIMIT 1
            """
        ),
        {"daily_plan_id": daily_plan_id},
    ).mappings().first()


def _get_first_pending_daily_plan_row(conn, goal_id: str):
    return conn.execute(
        text(
            """
            SELECT
                id,
                goal_id,
                day_number,
                planned_date,
                status,
                created_at
            FROM daily_plans
            WHERE goal_id = :goal_id
              AND status = 'pending'
            ORDER BY day_number ASC
            LIMIT 1
            """
        ),
        {"goal_id": goal_id},
    ).mappings().first()


def _get_next_pending_daily_plan_row_after(conn, goal_id: str, day_number: int):
    return conn.execute(
        text(
            """
            SELECT
                id,
                goal_id,
                day_number,
                planned_date,
                status,
                created_at
            FROM daily_plans
            WHERE goal_id = :goal_id
              AND status = 'pending'
              AND day_number > :day_number
            ORDER BY day_number ASC
            LIMIT 1
            """
        ),
        {
            "goal_id": goal_id,
            "day_number": day_number,
        },
    ).mappings().first()


def _get_next_cycle_index(conn, goal_id: str) -> int:
    row = conn.execute(
        text(
            """
            SELECT COALESCE(MAX(cycle_index), 0) AS max_cycle_index
            FROM daily_plan_cycles
            WHERE goal_id = :goal_id
            """
        ),
        {"goal_id": goal_id},
    ).mappings().one()

    return int(row["max_cycle_index"] or 0) + 1


def _load_goal_available_weekdays(conn, goal_id: str) -> set[int] | None:
    session = conn.execute(
        text(
            """
            SELECT context_json
            FROM goal_sessions
            WHERE goal_id = :goal_id
            LIMIT 1
            """
        ),
        {"goal_id": goal_id},
    ).mappings().first()

    if not session:
        return None

    context_json = session["context_json"] or {}
    if not isinstance(context_json, dict):
        return None

    profiling = context_json.get("profiling", {})
    if not isinstance(profiling, dict):
        profiling = {}

    profiling_summary = profiling.get("summary", {})
    if not isinstance(profiling_summary, dict):
        profiling_summary = {}

    answers = profiling.get("answers", {})
    if not isinstance(answers, dict):
        answers = {}

    candidates: list[Any] = [
        profiling_summary.get("available_days"),
        profiling_summary.get("preferred_days"),
        profiling_summary.get("free_days"),
        profiling_summary.get("weekdays"),
        profiling_summary.get("days_of_week"),
        profiling_summary.get("schedule_days"),
        answers.get("available_days"),
        answers.get("preferred_days"),
        answers.get("free_days"),
        answers.get("weekdays"),
        answers.get("days_of_week"),
        answers.get("schedule_days"),
    ]

    result: set[int] = set()
    for candidate in candidates:
        result.update(_extract_weekdays(candidate))

    return result or None


def _find_next_scheduled_date(
    *,
    allowed_weekdays: set[int] | None,
    start_date: date,
    strict_after: bool,
) -> date:
    if not allowed_weekdays:
        return start_date + timedelta(days=1) if strict_after else start_date

    current = start_date + timedelta(days=1) if strict_after else start_date

    for _ in range(14):
        if current.isoweekday() in allowed_weekdays:
            return current
        current += timedelta(days=1)

    return current


def _calculate_initial_cycle_due_at(
    *,
    conn,
    goal_id: str,
    daily_plan_row,
) -> datetime:
    allowed_weekdays = _load_goal_available_weekdays(conn, goal_id)

    planned_date = _parse_date(daily_plan_row["planned_date"])
    today_utc = datetime.now(timezone.utc).date()

    anchor_date = planned_date or today_utc
    if anchor_date < today_utc:
        anchor_date = today_utc

    due_date = _find_next_scheduled_date(
        allowed_weekdays=allowed_weekdays,
        start_date=anchor_date,
        strict_after=False,
    )
    return _end_of_day_utc(due_date)


def _calculate_next_cycle_due_at(
    *,
    conn,
    goal_id: str,
    from_date: date,
) -> datetime:
    allowed_weekdays = _load_goal_available_weekdays(conn, goal_id)

    due_date = _find_next_scheduled_date(
        allowed_weekdays=allowed_weekdays,
        start_date=from_date,
        strict_after=True,
    )
    return _end_of_day_utc(due_date)


def get_active_cycle(goal_id: str) -> dict[str, Any] | None:
    with engine.begin() as conn:
        row = conn.execute(
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
                  AND status = :status
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "status": ACTIVE_CYCLE_STATUS,
            },
        ).mappings().first()

        if not row:
            return None

        return _map_cycle_row(row)


def get_cycle_by_daily_plan_id(goal_id: str, daily_plan_id: str) -> dict[str, Any] | None:
    with engine.begin() as conn:
        row = conn.execute(
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
                  AND daily_plan_id = :daily_plan_id
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "daily_plan_id": daily_plan_id,
            },
        ).mappings().first()

        if not row:
            return None

        return _map_cycle_row(row)


def assign_first_cycle_for_goal(goal_id: str) -> dict[str, Any] | None:
    with engine.begin() as conn:
        existing_active = conn.execute(
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
                  AND status = :status
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "status": ACTIVE_CYCLE_STATUS,
            },
        ).mappings().first()

        if existing_active:
            return _map_cycle_row(existing_active)

        first_plan = _get_first_pending_daily_plan_row(conn, goal_id)
        if not first_plan:
            return None

        existing_for_plan = conn.execute(
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
                WHERE daily_plan_id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": str(first_plan["id"])},
        ).mappings().first()

        if existing_for_plan:
            return _map_cycle_row(existing_for_plan)

        due_at = _calculate_initial_cycle_due_at(
            conn=conn,
            goal_id=goal_id,
            daily_plan_row=first_plan,
        )
        cycle_index = _get_next_cycle_index(conn, goal_id)
        now_utc = datetime.now(timezone.utc)

        row = conn.execute(
            text(
                """
                INSERT INTO daily_plan_cycles (
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at
                )
                VALUES (
                    :goal_id,
                    :daily_plan_id,
                    :cycle_index,
                    :status,
                    :opened_at,
                    :due_at,
                    NULL
                )
                RETURNING
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
                """
            ),
            {
                "goal_id": goal_id,
                "daily_plan_id": str(first_plan["id"]),
                "cycle_index": cycle_index,
                "status": ACTIVE_CYCLE_STATUS,
                "opened_at": now_utc,
                "due_at": due_at,
            },
        ).mappings().one()

        return _map_cycle_row(row)


def complete_cycle_for_daily_plan(daily_plan_id: str) -> dict[str, Any] | None:
    with engine.begin() as conn:
        cycle_row = conn.execute(
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
                WHERE daily_plan_id = :daily_plan_id
                  AND status = :status
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "daily_plan_id": daily_plan_id,
                "status": ACTIVE_CYCLE_STATUS,
            },
        ).mappings().first()

        if not cycle_row:
            return None

        completed_at = datetime.now(timezone.utc)

        row = conn.execute(
            text(
                """
                UPDATE daily_plan_cycles
                SET
                    status = :new_status,
                    completed_at = :completed_at,
                    updated_at = NOW()
                WHERE id = :cycle_id
                RETURNING
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
                """
            ),
            {
                "cycle_id": str(cycle_row["id"]),
                "new_status": COMPLETED_CYCLE_STATUS,
                "completed_at": completed_at,
            },
        ).mappings().one()

        return _map_cycle_row(row)


def unlock_next_cycle_after_completion(
    goal_id: str,
    completed_daily_plan_id: str,
) -> dict[str, Any] | None:
    with engine.begin() as conn:
        existing_active = conn.execute(
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
                  AND status = :status
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "status": ACTIVE_CYCLE_STATUS,
            },
        ).mappings().first()

        if existing_active:
            return _map_cycle_row(existing_active)

        completed_plan_row = _get_daily_plan_row(conn, completed_daily_plan_id)
        if not completed_plan_row:
            return None

        next_plan = _get_next_pending_daily_plan_row_after(
            conn,
            goal_id=goal_id,
            day_number=int(completed_plan_row["day_number"]),
        )
        if not next_plan:
            return None

        existing_for_next = conn.execute(
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
                WHERE daily_plan_id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": str(next_plan["id"])},
        ).mappings().first()

        if existing_for_next:
            return _map_cycle_row(existing_for_next)

        reference_date = datetime.now(timezone.utc).date()
        due_at = _calculate_next_cycle_due_at(
            conn=conn,
            goal_id=goal_id,
            from_date=reference_date,
        )
        cycle_index = _get_next_cycle_index(conn, goal_id)
        now_utc = datetime.now(timezone.utc)

        row = conn.execute(
            text(
                """
                INSERT INTO daily_plan_cycles (
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at
                )
                VALUES (
                    :goal_id,
                    :daily_plan_id,
                    :cycle_index,
                    :status,
                    :opened_at,
                    :due_at,
                    NULL
                )
                RETURNING
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
                """
            ),
            {
                "goal_id": goal_id,
                "daily_plan_id": str(next_plan["id"]),
                "cycle_index": cycle_index,
                "status": ACTIVE_CYCLE_STATUS,
                "opened_at": now_utc,
                "due_at": due_at,
            },
        ).mappings().one()

        return _map_cycle_row(row)


def unlock_next_cycle_after_missed(
    goal_id: str,
    missed_daily_plan_id: str,
) -> dict[str, Any] | None:
    with engine.begin() as conn:
        existing_active = conn.execute(
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
                  AND status = :status
                ORDER BY cycle_index ASC
                LIMIT 1
                """
            ),
            {
                "goal_id": goal_id,
                "status": ACTIVE_CYCLE_STATUS,
            },
        ).mappings().first()

        if existing_active:
            return _map_cycle_row(existing_active)

        missed_plan_row = _get_daily_plan_row(conn, missed_daily_plan_id)
        if not missed_plan_row:
            return None

        next_plan = _get_next_pending_daily_plan_row_after(
            conn,
            goal_id=goal_id,
            day_number=int(missed_plan_row["day_number"]),
        )
        if not next_plan:
            return None

        existing_for_next = conn.execute(
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
                WHERE daily_plan_id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": str(next_plan["id"])},
        ).mappings().first()

        if existing_for_next:
            return _map_cycle_row(existing_for_next)

        reference_date = datetime.now(timezone.utc).date()
        due_at = _calculate_next_cycle_due_at(
            conn=conn,
            goal_id=goal_id,
            from_date=reference_date,
        )
        cycle_index = _get_next_cycle_index(conn, goal_id)
        now_utc = datetime.now(timezone.utc)

        row = conn.execute(
            text(
                """
                INSERT INTO daily_plan_cycles (
                    goal_id,
                    daily_plan_id,
                    cycle_index,
                    status,
                    opened_at,
                    due_at,
                    completed_at
                )
                VALUES (
                    :goal_id,
                    :daily_plan_id,
                    :cycle_index,
                    :status,
                    :opened_at,
                    :due_at,
                    NULL
                )
                RETURNING
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
                """
            ),
            {
                "goal_id": goal_id,
                "daily_plan_id": str(next_plan["id"]),
                "cycle_index": cycle_index,
                "status": ACTIVE_CYCLE_STATUS,
                "opened_at": now_utc,
                "due_at": due_at,
            },
        ).mappings().one()

        return _map_cycle_row(row)


def mark_overdue_cycles(now: datetime | None = None) -> list[dict[str, Any]]:
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
                WHERE status = :status
                  AND due_at < :now_utc
                ORDER BY due_at ASC
                """
            ),
            {
                "status": ACTIVE_CYCLE_STATUS,
                "now_utc": now,
            },
        ).mappings().all()

    updated_cycles: list[dict[str, Any]] = []

    for row in rows:
        with engine.begin() as conn:
            fresh_row = conn.execute(
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
                    WHERE id = :cycle_id
                    LIMIT 1
                    """
                ),
                {"cycle_id": str(row["id"])},
            ).mappings().first()

            if not fresh_row:
                continue

            if fresh_row["status"] != ACTIVE_CYCLE_STATUS:
                continue

            updated_row = conn.execute(
                text(
                    """
                    UPDATE daily_plan_cycles
                    SET
                        status = :new_status,
                        updated_at = NOW()
                    WHERE id = :cycle_id
                    RETURNING
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
                    """
                ),
                {
                    "cycle_id": str(fresh_row["id"]),
                    "new_status": MISSED_CYCLE_STATUS,
                },
            ).mappings().one()

            conn.execute(
                text(
                    """
                    UPDATE daily_plans
                    SET
                        status = 'skipped',
                        updated_at = NOW()
                    WHERE id = :daily_plan_id
                      AND status IN ('pending', 'in_progress')
                    """
                ),
                {"daily_plan_id": str(fresh_row["daily_plan_id"])},
            )

            conn.execute(
                text(
                    """
                    UPDATE daily_tasks
                    SET
                        status = 'skipped',
                        updated_at = NOW()
                    WHERE daily_plan_id = :daily_plan_id
                      AND status = 'pending'
                    """
                ),
                {"daily_plan_id": str(fresh_row["daily_plan_id"])},
            )

            updated_cycles.append(_map_cycle_row(updated_row))

            unlock_next_cycle_after_missed(
                goal_id=str(fresh_row["goal_id"]),
                missed_daily_plan_id=str(fresh_row["daily_plan_id"]),
            )

    return updated_cycles