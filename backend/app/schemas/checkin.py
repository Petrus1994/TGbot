from datetime import date, datetime
from pydantic import BaseModel


class CheckinReportRequest(BaseModel):
    report_text: str


class CheckinStepStatusRequest(BaseModel):
    status: str  # pending | done | failed


class CheckinStepStatusResponse(BaseModel):
    step_id: str
    status: str


class CheckinResponse(BaseModel):
    checkin_id: str
    goal_id: str
    checkin_date: date
    status: str  # open | completed
    report_text: str | None = None
    steps: list[CheckinStepStatusResponse]
    created_at: datetime
    updated_at: datetime


class CompleteCheckinResponse(BaseModel):
    success: bool
    checkin: CheckinResponse