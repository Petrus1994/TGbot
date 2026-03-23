from fastapi import APIRouter, HTTPException, status

from app.schemas.checkin import (
    CheckinReportRequest,
    CheckinResponse,
    CheckinStepStatusRequest,
    CompleteCheckinResponse,
)
from app.services.checkin_service import (
    complete_checkin,
    create_or_get_today_checkin,
    get_today_checkin,
    save_checkin_report,
    set_step_status,
)

router = APIRouter(tags=["checkins"])


@router.post(
    "/goals/{goal_id}/checkins/today",
    response_model=CheckinResponse,
    status_code=status.HTTP_200_OK,
)
def create_or_get_today_checkin_endpoint(goal_id: str):
    try:
        return create_or_get_today_checkin(goal_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get(
    "/goals/{goal_id}/checkins/today",
    response_model=CheckinResponse,
)
def get_today_checkin_endpoint(goal_id: str):
    checkin = get_today_checkin(goal_id)
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found.")
    return checkin


@router.post(
    "/checkins/{checkin_id}/report",
    response_model=CheckinResponse,
)
def save_checkin_report_endpoint(checkin_id: str, payload: CheckinReportRequest):
    try:
        return save_checkin_report(checkin_id, payload.report_text)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post(
    "/checkins/{checkin_id}/steps/{step_id}/status",
    response_model=CheckinResponse,
)
def set_step_status_endpoint(
    checkin_id: str,
    step_id: str,
    payload: CheckinStepStatusRequest,
):
    try:
        return set_step_status(checkin_id, step_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post(
    "/checkins/{checkin_id}/complete",
    response_model=CompleteCheckinResponse,
)
def complete_checkin_endpoint(checkin_id: str):
    try:
        return complete_checkin(checkin_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e