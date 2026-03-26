from datetime import datetime
from pydantic import BaseModel

from app.models.proof import ProofStatus, ProofType


class CreateProofRequest(BaseModel):
    goal_id: str | None = None
    telegram_file_id: str | None = None
    file_unique_id: str | None = None
    proof_type: ProofType
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    text: str | None = None


class UpdateProofStatusRequest(BaseModel):
    status: ProofStatus


class ProofResponse(BaseModel):
    proof_id: str
    goal_id: str
    checkin_id: str
    step_id: str
    proof_type: ProofType
    telegram_file_id: str | None = None
    file_unique_id: str | None = None
    mime_type: str | None = None
    filename: str | None = None
    caption: str | None = None
    text: str | None = None
    status: ProofStatus
    created_at: datetime
    updated_at: datetime