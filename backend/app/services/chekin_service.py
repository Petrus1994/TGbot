from datetime import date, datetime, timezone

from app.schemas.checkin import (
    CheckinResponse,
    CheckinStepStatusResponse,
    CompleteCheckinResponse,
)
from app.services.plan_service import get_current_plan

_CHECKIN_STORE: dict[str, dict] = {}


def _today_key(goal_id: str) -> str:
    return f"{goal_id}:{date.today().isoformat()}"


def create_or_get_today_checkin(goal_id: str) -> CheckinResponse:
    key = _today_key(goal_id)

    if key in _CHECKIN_STORE:
        return CheckinResponse(**_CHECKIN_STORE[key])

    plan = get_current_plan(goal_id)
    if not plan:
        raise ValueError("Plan not found for this goal.")

    now = datetime.now(timezone.utc)
    steps = [
        {
            "step_id": step.step_id,
            "status": "pending",
        }
        for step in plan.content.steps
    ]

    checkin = {
        "checkin_id": f"{goal_id}-{date.today().isoformat()}",
        "goal_id": goal_id,
        "checkin_date": date.today(),
        "status": "open",
        "report_text": None,
        "steps": steps,
        "created_at": now,
        "updated_at": now,
    }

    _CHECKIN_STORE[key] = checkin
    return CheckinResponse(**checkin)


def get_today_checkin(goal_id: str) -> CheckinResponse | None:
    key = _today_key(goal_id)
    data = _CHECKIN_STORE.get(key)
    if not data:
        return None
    return CheckinResponse(**data)


def save_checkin_report(checkin_id: str, report_text: str) -> CheckinResponse:
    checkin = _find_checkin_by_id(checkin_id)
    if not checkin:
        raise ValueError("Check-in not found.")

    checkin["report_text"] = report_text
    checkin["updated_at"] = datetime.now(timezone.utc)

    return CheckinResponse(**checkin)


def set_step_status(checkin_id: str, step_id: str, status: str) -> CheckinResponse:
    if status not in {"done", "failed"}:
        raise ValueError("Invalid status. Use 'done' or 'failed'.")

    checkin = _find_checkin_by_id(checkin_id)
    if not checkin:
        raise ValueError("Check-in not found.")

    for step in checkin["steps"]:
        if step["step_id"] == step_id:
            step["status"] = status
            checkin["updated_at"] = datetime.now(timezone.utc)
            return CheckinResponse(**checkin)

    raise ValueError("Step not found in this check-in.")


def complete_checkin(checkin_id: str) -> CompleteCheckinResponse:
    checkin = _find_checkin_by_id(checkin_id)
    if not checkin:
        raise ValueError("Check-in not found.")

    checkin["status"] = "completed"
    checkin["updated_at"] = datetime.now(timezone.utc)

    return CompleteCheckinResponse(
        success=True,
        checkin=CheckinResponse(**checkin),
    )


def _find_checkin_by_id(checkin_id: str) -> dict | None:
    for value in _CHECKIN_STORE.values():
        if value["checkin_id"] == checkin_id:
            return value
    return None