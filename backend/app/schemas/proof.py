from datetime import datetime
from pydantic import BaseModel

from app.models.proof import ProofStatus, ProofType


class CreateProofRequest(BaseModel):
    telegram_file_id: str | None = None
    file_unique_id: str | None = None
    proof_type: ProofType
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    text: str | None = None


class ReviewProofRequest(BaseModel):
    status: ProofStatus
    review_message: str | None = None


class ProofResponse(BaseModel):
    proof_id: str
    goal_id: str
    daily_plan_id: str
    daily_task_id: str

    proof_type: ProofType
    telegram_file_id: str | None = None
    file_unique_id: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    text: str | None = None

    status: ProofStatus
    review_message: str | None = None

    submitted_at: datetime
    reviewed_at: datetime | None = None
    created_at: datetime