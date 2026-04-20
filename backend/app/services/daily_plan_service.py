from __future__ import annotations

import json
import re
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
from app.schemas.goal_generation import GoalGenerationContext
from app.services.daily_cycle_service import (
    assign_first_cycle_for_goal,
    complete_cycle_for_daily_plan,
    get_active_cycle,
    unlock_next_cycle_after_completion,
)
from app.services.daily_task_detailing_service import DailyTaskDetailingService
from app.services.proof_service import (
    daily_plan_all_required_proofs_present,
    list_task_proofs,
    task_has_required_proof,
)

# =========================================================
# 🔥 EXECUTION INTELLIGENCE LAYER (SAFE ADDITION)
# =========================================================

def _calculate_day_difficulty(plan: DailyPlanResponse) -> str:
    total = plan.total_estimated_minutes or 0

    if total <= 30:
        return "easy"
    if total <= 90:
        return "medium"
    return "hard"


def _prioritize_tasks(tasks: list[DailyTaskResponse]) -> list[DailyTaskResponse]:
    def score(task: DailyTaskResponse):
        s = 0

        if task.is_required:
            s += 10

        if task.priority == "high":
            s += 5

        if task.priority == "low":
            s -= 2

        if task.estimated_minutes:
            s -= min(task.estimated_minutes / 30, 3)

        if task.proof_required:
            s += 1

        return s

    return sorted(tasks, key=score, reverse=True)


def _inject_minimum_execution_fields(task: DailyTaskResponse) -> None:
    """
    Гарантируем что таска всегда исполнима
    """

    if not task.why_today:
        task.why_today = "Это действие напрямую двигает тебя к цели."

    if not task.success_criteria:
        task.success_criteria = "Задача завершена полностью."

    if task.estimated_minutes is None:
        task.estimated_minutes = 15


def _ensure_tasks_are_executable(tasks: list[DailyTaskResponse]) -> list[DailyTaskResponse]:
    for t in tasks:
        _inject_minimum_execution_fields(t)
    return tasks


def _build_focus_message(plan: DailyPlanResponse) -> str:
    if not plan.tasks:
        return "Сделай хотя бы одно действие по цели."

    main = plan.tasks[0]
    return f"Главный фокус: {main.title}"


def _build_headline(plan: DailyPlanResponse) -> str:
    return f"День {plan.day_number}: {plan.focus or 'Execution'}"

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


def _safe_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return []


def _safe_json_array(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def _parse_task_steps(value: Any) -> list[DailyTaskStepResponse]:
    raw_steps = _safe_json_array(value)
    parsed_steps: list[DailyTaskStepResponse] = []

    for item in raw_steps:
        if not isinstance(item, dict):
            continue

        title = str(item.get("title") or "").strip()
        instruction = str(item.get("instruction") or "").strip()
        if not title or not instruction:
            continue

        parsed_steps.append(
            DailyTaskStepResponse(
                order=int(item.get("order") or 1),
                title=title,
                instruction=instruction,
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
    raw_resources = _safe_json_array(value)
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

    tasks: list[DailyTaskResponse] = []

    for row in rows:
        proofs = list_task_proofs(str(row["id"]))

        tasks.append(
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
                    for item in _safe_json_array(row["tips"])
                    if str(item).strip()
                ],
                technique_cues=[
                    str(item)
                    for item in _safe_json_array(row["technique_cues"])
                    if str(item).strip()
                ],
                common_mistakes=[
                    str(item)
                    for item in _safe_json_array(row["common_mistakes"])
                    if str(item).strip()
                ],
                steps=_parse_task_steps(row["steps"]),
                resources=_parse_task_resources(row["resources"]),
                proofs=proofs,
                status=DailyTaskStatus(row["status"]),
                completed_at=row["completed_at"],
                created_at=row["created_at"],
            )
        )

    return tasks


def _build_daily_plan_response(conn, row) -> DailyPlanResponse:
    tasks = _get_tasks_for_daily_plan(conn, str(row["id"]))

    # 🔥 NEW: приоритизация
    tasks = _prioritize_tasks(tasks)

    # 🔥 NEW: гарантия исполнимости
    tasks = _ensure_tasks_are_executable(tasks)

    proofs_required_count = sum(1 for task in tasks if task.proof_required)
    proofs_accepted_count = sum(
        1 for task in tasks if task.proof_required and task_has_required_proof(task.id)
    )

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
        proofs_required_count=proofs_required_count,
        proofs_accepted_count=proofs_accepted_count,
        created_at=row["created_at"],
    )
    tasks = _get_tasks_for_daily_plan(conn, str(row["id"]))

    proofs_required_count = sum(1 for task in tasks if task.proof_required)
    proofs_accepted_count = sum(
        1 for task in tasks if task.proof_required and task_has_required_proof(task.id)
    )

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
        proofs_required_count=proofs_required_count,
        proofs_accepted_count=proofs_accepted_count,
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
            parsed_planned_date = _parse_date(day.planned_date) or date.today()

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
                        "tips": json.dumps(task.tips, ensure_ascii=False),
                        "technique_cues": json.dumps(
                            task.technique_cues, ensure_ascii=False
                        ),
                        "common_mistakes": json.dumps(
                            task.common_mistakes, ensure_ascii=False
                        ),
                        "steps": json.dumps(
                            [step.model_dump() for step in task.steps],
                            ensure_ascii=False,
                        ),
                        "resources": json.dumps(
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


def get_daily_plan_by_day_number(
    goal_id: str,
    day_number: int,
) -> DailyPlanResponse | None:
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


def get_daily_plan_by_id(daily_plan_id: str) -> DailyPlanResponse | None:
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
                WHERE id = :daily_plan_id
                LIMIT 1
                """
            ),
            {"daily_plan_id": daily_plan_id},
        ).mappings().first()

        if not row:
            return None

        return _build_daily_plan_response(conn, row)


def get_active_cycle_daily_plan(goal_id: str) -> DailyPlanResponse | None:
    active_cycle = get_active_cycle(goal_id)
    if not active_cycle:
        return None

    return get_daily_plan_by_id(active_cycle["daily_plan_id"])


def _load_goal_available_weekdays(goal_id: str) -> set[int] | None:
    with engine.begin() as connection:
        session = connection.execute(
            text(
                """
                SELECT context_json
                FROM goal_sessions
                WHERE goal_id = :goal_id
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


def _is_goal_allowed_for_date(goal_id: str, target_date: date) -> bool:
    allowed_weekdays = _load_goal_available_weekdays(goal_id)
    if not allowed_weekdays:
        return True
    return target_date.isoweekday() in allowed_weekdays


def get_today_plan(
    goal_id: str,
    today_date: date | None = None,
) -> DailyPlanResponse | None:
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
                  AND status IN ('pending', 'in_progress')
                ORDER BY planned_date DESC, day_number DESC
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

def get_next_actionable_daily_plan(
    goal_id: str,
    reference_date: date | None = None,
) -> DailyPlanResponse | None:
    reference_date = reference_date or date.today()

    active_cycle_plan = get_active_cycle_daily_plan(goal_id)
    if active_cycle_plan:
        return active_cycle_plan

    assigned_cycle = assign_first_cycle_for_goal(goal_id)
    if assigned_cycle:
        return get_daily_plan_by_id(assigned_cycle["daily_plan_id"])

    with engine.begin() as conn:
        pending_rows = conn.execute(
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
                  AND status = 'pending'
                ORDER BY day_number ASC
                """
            ),
            {"goal_id": goal_id},
        ).mappings().all()

        if not pending_rows:
            return None

        started_row = conn.execute(
            text(
                """
                SELECT id
                FROM daily_plans
                WHERE goal_id = :goal_id
                  AND status IN ('done', 'skipped', 'in_progress')
                LIMIT 1
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not started_row:
            return _build_daily_plan_response(conn, pending_rows[0])

        if not _is_goal_allowed_for_date(goal_id, reference_date):
            return None

        return _build_daily_plan_response(conn, pending_rows[0])


def update_daily_task_status(
    task_id: str,
    status: DailyTaskStatus,
) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        task_row = conn.execute(
            text(
                """
                SELECT
                    id,
                    daily_plan_id,
                    proof_required
                FROM daily_tasks
                WHERE id = :task_id
                LIMIT 1
                """
            ),
            {"task_id": task_id},
        ).mappings().first()

        if not task_row:
            return None

        if status == DailyTaskStatus.done and bool(task_row["proof_required"]):
            if not task_has_required_proof(task_id):
                raise ValueError("required_proof_missing_for_task")

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

    updated_plan = recalculate_daily_plan_status(str(task_row["daily_plan_id"]))
    if not updated_plan:
        return None

    if updated_plan.status == DailyPlanStatus.done:
        complete_cycle_for_daily_plan(updated_plan.id)
        unlock_next_cycle_after_completion(
            goal_id=updated_plan.goal_id,
            completed_daily_plan_id=updated_plan.id,
        )
        refreshed_active = get_active_cycle_daily_plan(updated_plan.goal_id)
        if refreshed_active:
            return refreshed_active

    return updated_plan


def update_daily_plan_status(
    daily_plan_id: str,
    status: DailyPlanStatus,
) -> DailyPlanResponse | None:
    with engine.begin() as conn:
        if status == DailyPlanStatus.done:
            if not daily_plan_all_required_proofs_present(daily_plan_id):
                raise ValueError("required_proofs_missing_for_daily_plan")

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

        updated_plan = _build_daily_plan_response(conn, row)

    if updated_plan.status == DailyPlanStatus.done:
        complete_cycle_for_daily_plan(updated_plan.id)
        unlock_next_cycle_after_completion(
            goal_id=updated_plan.goal_id,
            completed_daily_plan_id=updated_plan.id,
        )
        refreshed_active = get_active_cycle_daily_plan(updated_plan.goal_id)
        if refreshed_active:
            return refreshed_active

    return updated_plan


def _daily_plan_needs_detailing(plan: DailyPlanResponse) -> bool:
    if not plan.headline:
        return True
    if not plan.main_task_title:
        return True
    if plan.total_estimated_minutes is None:
        return True
    if not plan.tasks:
        return True

    for task in plan.tasks:
        if task.is_required:
            if not task.why_today:
                return True
            if not task.success_criteria:
                return True
            if task.proof_required and not task.proof_prompt:
                return True
            if task.detail_level >= 2 and not task.steps:
                return True

    return False


def _normalize_text_field(value: Any) -> str | None:
    if value is None:
        return None

    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(items) if items else None

    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            key_str = str(key).strip()
            item_str = str(item).strip()
            if key_str and item_str:
                parts.append(f"{key_str}: {item_str}")
        return "; ".join(parts) if parts else None

    value = str(value).strip()
    return value or None


def _pick_first_non_empty(*values: Any) -> str | None:
    for value in values:
        normalized = _normalize_text_field(value)
        if normalized:
            return normalized
    return None


def _infer_response_language(context: GoalGenerationContext) -> str:
    text_parts = [
        context.goal_title,
        context.goal_description,
        context.current_level,
        context.constraints,
        context.resources,
        context.motivation,
        context.coach_style,
        context.goal_outcome,
        context.time_budget,
        context.main_obstacles,
        context.daily_routine,
    ]
    combined = " ".join(part for part in text_parts if part)

    for ch in combined:
        if "А" <= ch <= "я" or ch in {"Ё", "ё"}:
            return "Russian"
    return "English"


def _load_goal_generation_context(goal_id: str) -> GoalGenerationContext:
    with engine.begin() as connection:
        goal = connection.execute(
            text(
                """
                SELECT id, user_id, title, description, target_date
                FROM goals
                WHERE id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not goal:
            raise ValueError("goal_not_found")

        session = connection.execute(
            text(
                """
                SELECT context_json
                FROM goal_sessions
                WHERE goal_id = :goal_id
                """
            ),
            {"goal_id": goal_id},
        ).mappings().first()

        if not session:
            raise ValueError("profiling_not_started")

        context_json = session["context_json"] or {}
        if not isinstance(context_json, dict):
            context_json = {}

        profiling = context_json.get("profiling", {})
        if not isinstance(profiling, dict):
            profiling = {}

        profiling_summary = profiling.get("summary", {})
        if not isinstance(profiling_summary, dict):
            profiling_summary = {}

        answers = profiling.get("answers", {})
        if not isinstance(answers, dict):
            answers = {}

        current_level = _pick_first_non_empty(
            profiling_summary.get("current_state"),
            profiling_summary.get("current_level"),
            answers.get("current_state"),
            answers.get("current_level"),
        )
        constraints = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("constraints"),
                answers.get("constraints"),
            )
        )
        resources = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("resources"),
                answers.get("resources"),
            )
        )
        motivation = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("motivation"),
                answers.get("motivation"),
            )
        )
        coach_style = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("coach_style"),
                answers.get("coach_style"),
                profiling_summary.get("preferred_execution_style"),
                answers.get("preferred_execution_style"),
            )
        )

        goal_outcome = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("goal_outcome"),
                profiling_summary.get("success_metrics"),
                answers.get("goal_outcome"),
            )
        )
        deadline = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("deadline"),
                answers.get("deadline"),
                goal.get("target_date"),
            )
        )
        time_budget = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("time_budget"),
                answers.get("time_budget"),
            )
        )
        past_attempts = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("past_attempts"),
                answers.get("past_attempts"),
            )
        )
        main_obstacles = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("main_obstacles"),
                profiling_summary.get("risk_factors"),
                answers.get("main_obstacles"),
            )
        )
        daily_routine = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("daily_routine"),
                answers.get("daily_routine"),
            )
        )
        planning_notes = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("planning_notes"),
                profiling_summary.get("environment"),
                answers.get("planning_notes"),
            )
        )
        plan_confidence = _normalize_text_field(
            _pick_first_non_empty(
                profiling_summary.get("plan_confidence"),
            )
        )

        return GoalGenerationContext(
            goal_id=str(goal["id"]),
            user_id=str(goal["user_id"]),
            goal_title=goal.get("title") or "Untitled goal",
            goal_description=goal.get("description"),
            current_level=current_level,
            constraints=constraints,
            resources=resources,
            motivation=motivation,
            coach_style=coach_style,
            goal_outcome=goal_outcome,
            deadline=deadline,
            time_budget=time_budget,
            past_attempts=past_attempts,
            main_obstacles=main_obstacles,
            daily_routine=daily_routine,
            planning_notes=planning_notes,
            plan_confidence=plan_confidence,
            profiling_summary=profiling_summary,
            profiling_answers=answers,
        )


def _build_day_payload_from_plan(plan: DailyPlanResponse) -> dict[str, Any]:
    return {
        "day_number": plan.day_number,
        "planned_date": plan.planned_date.isoformat() if plan.planned_date else None,
        "focus": plan.focus,
        "summary": plan.summary,
        "headline": plan.headline,
        "focus_message": plan.focus_message,
        "main_task_title": plan.main_task_title,
        "total_estimated_minutes": plan.total_estimated_minutes,
        "tasks": [
            {
                "title": task.title,
                "description": task.description,
                "objective": task.objective,
                "instructions": task.instructions,
                "why_today": task.why_today,
                "success_criteria": task.success_criteria,
                "estimated_minutes": task.estimated_minutes,
                "detail_level": task.detail_level,
                "bucket": task.bucket,
                "priority": task.priority,
                "is_required": task.is_required,
                "proof_required": task.proof_required,
                "recommended_proof_type": task.recommended_proof_type,
                "proof_prompt": task.proof_prompt,
                "task_type": task.task_type,
                "difficulty": task.difficulty,
                "tips": task.tips,
                "technique_cues": task.technique_cues,
                "common_mistakes": task.common_mistakes,
                "steps": [step.model_dump() for step in task.steps],
                "resources": [resource.model_dump() for resource in task.resources],
            }
            for task in plan.tasks
        ],
    }


def _update_detailed_daily_plan(
    daily_plan_id: str,
    detailed_day: dict[str, Any],
) -> None:
    tasks = detailed_day.get("tasks", [])

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE daily_plans
                SET headline = :headline,
                    focus_message = :focus_message,
                    main_task_title = :main_task_title,
                    total_estimated_minutes = :total_estimated_minutes,
                    updated_at = NOW()
                WHERE id = :daily_plan_id
                """
            ),
            {
                "daily_plan_id": daily_plan_id,
                "headline": detailed_day.get("headline"),
                "focus_message": detailed_day.get("focus_message"),
                "main_task_title": detailed_day.get("main_task_title"),
                "total_estimated_minutes": detailed_day.get("total_estimated_minutes"),
            },
        )

        for index, task in enumerate(tasks, start=1):
            conn.execute(
                text(
                    """
                    UPDATE daily_tasks
                    SET
                        title = :title,
                        objective = :objective,
                        description = :description,
                        instructions = :instructions,
                        why_today = :why_today,
                        success_criteria = :success_criteria,
                        estimated_minutes = :estimated_minutes,
                        detail_level = :detail_level,
                        bucket = :bucket,
                        priority = :priority,
                        is_required = :is_required,
                        proof_required = :proof_required,
                        recommended_proof_type = :recommended_proof_type,
                        proof_prompt = :proof_prompt,
                        task_type = :task_type,
                        difficulty = :difficulty,
                        tips = CAST(:tips AS JSONB),
                        technique_cues = CAST(:technique_cues AS JSONB),
                        common_mistakes = CAST(:common_mistakes AS JSONB),
                        steps = CAST(:steps AS JSONB),
                        resources = CAST(:resources AS JSONB),
                        updated_at = NOW()
                    WHERE daily_plan_id = :daily_plan_id
                      AND order_index = :order_index
                    """
                ),
                {
                    "daily_plan_id": daily_plan_id,
                    "order_index": index,
                    "title": task.get("title"),
                    "objective": task.get("objective"),
                    "description": task.get("description"),
                    "instructions": task.get("instructions"),
                    "why_today": task.get("why_today"),
                    "success_criteria": task.get("success_criteria"),
                    "estimated_minutes": task.get("estimated_minutes"),
                    "detail_level": task.get("detail_level", 1),
                    "bucket": task.get("bucket", "must"),
                    "priority": task.get("priority", "medium"),
                    "is_required": bool(task.get("is_required", True)),
                    "proof_required": bool(task.get("proof_required", False)),
                    "recommended_proof_type": task.get("recommended_proof_type"),
                    "proof_prompt": task.get("proof_prompt"),
                    "task_type": task.get("task_type"),
                    "difficulty": task.get("difficulty"),
                    "tips": json.dumps(task.get("tips", []), ensure_ascii=False),
                    "technique_cues": json.dumps(
                        task.get("technique_cues", []), ensure_ascii=False
                    ),
                    "common_mistakes": json.dumps(
                        task.get("common_mistakes", []), ensure_ascii=False
                    ),
                    "steps": json.dumps(task.get("steps", []), ensure_ascii=False),
                    "resources": json.dumps(task.get("resources", []), ensure_ascii=False),
                },
            )


async def _safe_enrich_day(
    detailing_service: DailyTaskDetailingService,
    context: GoalGenerationContext,
    day_payload: dict[str, Any],
    response_language: str,
) -> dict[str, Any] | None:
    for _ in range(2):
        try:
            result = await detailing_service.enrich_single_day(
                context=context,
                day=day_payload,
                response_language=response_language,
            )
            if result and isinstance(result, dict) and result.get("tasks"):
                return result
        except Exception:
            continue

    return None


async def enrich_today_plan_if_needed(
    goal_id: str,
    today_date: date | None = None,
) -> DailyPlanResponse | None:

    plan = get_today_plan(goal_id, today_date=today_date)
    if not plan:
        return None

    if plan.status == DailyPlanStatus.done:
        return plan

    # 🔥 PRIORITY LAYER
    plan.tasks = _prioritize_tasks(plan.tasks)
    plan.tasks = _ensure_tasks_are_executable(plan.tasks)

    # 🤖 DETAILING (как было)
    if _daily_plan_needs_detailing(plan):
        try:
            context = _load_goal_generation_context(goal_id)
            response_language = _infer_response_language(context)
            day_payload = _build_day_payload_from_plan(plan)

            detailing_service = DailyTaskDetailingService()

            detailed_day = await _safe_enrich_day(
                detailing_service=detailing_service,
                context=context,
                day_payload=day_payload,
                response_language=response_language,
            )

            if detailed_day and isinstance(detailed_day, dict) and detailed_day.get("tasks"):
                _update_detailed_daily_plan(plan.id, detailed_day)

                refreshed_plan = get_daily_plan_by_id(plan.id)
                if refreshed_plan:
                    plan = refreshed_plan

        except Exception as e:
            print(f"⚠️ enrich_today_plan_if_needed failed: {e}")

    # 🔥 COACH UX LAYER
    if not plan.headline:
        plan.headline = _build_headline(plan)

    if not plan.focus_message:
        plan.focus_message = _build_focus_message(plan)

    return plan


async def enrich_today_plan_if_needed(
    goal_id: str,
    today_date: date | None = None,
) -> DailyPlanResponse | None:

    plan = get_today_plan(goal_id, today_date=today_date)
    if not plan:
        return None

    if plan.status == DailyPlanStatus.done:
        return plan

    # 🔥 PRIORITY LAYER
    plan.tasks = _prioritize_tasks(plan.tasks)
    plan.tasks = _ensure_tasks_are_executable(plan.tasks)

    # 🤖 DETAILING (как было)
    if _daily_plan_needs_detailing(plan):
        try:
            context = _load_goal_generation_context(goal_id)
            response_language = _infer_response_language(context)
            day_payload = _build_day_payload_from_plan(plan)

            detailing_service = DailyTaskDetailingService()

            detailed_day = await _safe_enrich_day(
                detailing_service=detailing_service,
                context=context,
                day_payload=day_payload,
                response_language=response_language,
            )

            if detailed_day and isinstance(detailed_day, dict) and detailed_day.get("tasks"):
                _update_detailed_daily_plan(plan.id, detailed_day)

                refreshed_plan = get_daily_plan_by_id(plan.id)
                if refreshed_plan:
                    plan = refreshed_plan

        except Exception as e:
            print(f"⚠️ enrich_today_plan_if_needed failed: {e}")

    # 🔥 COACH UX LAYER
    if not plan.headline:
        plan.headline = _build_headline(plan)

    if not plan.focus_message:
        plan.focus_message = _build_focus_message(plan)

    return plan