from fastapi import APIRouter, HTTPException

from app.services.goal_service import get_goal_by_id
from app.services.checkin_service import _CHECKIN_STORE

router = APIRouter(tags=["progress"])


@router.get("/goals/{goal_id}/progress")
def get_goal_progress(goal_id: str):
    goal = get_goal_by_id(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")

    checkins = [
        c for c in _CHECKIN_STORE.values()
        if c["goal_id"] == goal_id
    ]

    total_steps = 0
    done_steps = 0
    failed_steps = 0

    for checkin in checkins:
        for step in checkin["steps"]:
            total_steps += 1
            if step["status"] == "done":
                done_steps += 1
            elif step["status"] == "failed":
                failed_steps += 1

    progress_percent = 0
    if total_steps > 0:
        progress_percent = int((done_steps / total_steps) * 100)

    # статус цели (очень простой MVP)
    status = "active"
    if total_steps > 0 and done_steps == total_steps:
        status = "completed"

    return {
        "goal_id": goal_id,
        "status": status,
        "progress_percent": progress_percent,
        "total_steps": total_steps,
        "done_steps": done_steps,
        "failed_steps": failed_steps,
    }