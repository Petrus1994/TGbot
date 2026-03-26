from fastapi import APIRouter, HTTPException

from app.services.goal_service import get_goal_by_id, get_goal_status
from app.services.checkin_service import _CHECKIN_STORE
from app.services.plan_service import get_current_plan

router = APIRouter(tags=["progress"])


@router.get("/goals/{goal_id}/progress")
def get_goal_progress_endpoint(goal_id: str):
    goal = get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="goal_not_found")

    plan = get_current_plan(goal_id)
    if not plan:
        raise HTTPException(status_code=404, detail="plan_not_found")

    total_steps = len(plan.content.steps)

    done_steps = 0
    failed_steps = 0

    checkins = [
        checkin
        for checkin in _CHECKIN_STORE.values()
        if checkin["goal_id"] == goal_id
    ]

    # Берем последний статус каждого step_id по всем check-in
    latest_step_status: dict[str, str] = {}

    for checkin in checkins:
        for step in checkin["steps"]:
            latest_step_status[step["step_id"]] = step["status"]

    for status in latest_step_status.values():
        if status == "done":
            done_steps += 1
        elif status == "failed":
            failed_steps += 1

    pending_steps = total_steps - done_steps - failed_steps
    if pending_steps < 0:
        pending_steps = 0

    completion_percent = 0
    if total_steps > 0:
        completion_percent = int((done_steps / total_steps) * 100)

    return {
        "goal_id": goal_id,
        "status": get_goal_status(goal_id),
        "total_steps": total_steps,
        "done_steps": done_steps,
        "failed_steps": failed_steps,
        "pending_steps": pending_steps,
        "completion_percent": completion_percent,
    }