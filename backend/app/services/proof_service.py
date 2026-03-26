from datetime import datetime, timezone
from uuid import uuid4

from app.models.proof import ProofStatus, ProofType
from app.schemas.proof import CreateProofRequest, ProofResponse
from app.services.checkin_service import _find_checkin_by_id

_PROOF_STORE: dict[str, dict] = {}


def create_proof(checkin_id: str, step_id: str, payload: CreateProofRequest) -> ProofResponse:
    checkin = _find_checkin_by_id(checkin_id)
    if not checkin:
        raise ValueError("Check-in not found.")

    step_exists = any(step["step_id"] == step_id for step in checkin["steps"])
    if not step_exists:
        raise ValueError("Step not found in this check-in.")

    if payload.proof_type != ProofType.text and not payload.telegram_file_id:
        raise ValueError("telegram_file_id is required for photo/screenshot/file proof.")

    if payload.proof_type == ProofType.text and not payload.text:
        raise ValueError("text is required for text proof.")

    now = datetime.now(timezone.utc)
    proof_id = str(uuid4())

    proof = {
        "proof_id": proof_id,
        "goal_id": payload.goal_id or checkin["goal_id"],
        "checkin_id": checkin_id,
        "step_id": step_id,
        "proof_type": payload.proof_type,
        "telegram_file_id": payload.telegram_file_id,
        "file_unique_id": payload.file_unique_id,
        "mime_type": payload.mime_type,
        "filename": payload.filename,
        "caption": payload.caption,
        "text": payload.text,
        "status": ProofStatus.uploaded,
        "created_at": now,
        "updated_at": now,
    }

    _PROOF_STORE[proof_id] = proof
    return ProofResponse(**proof)


def list_checkin_proofs(checkin_id: str) -> list[ProofResponse]:
    proofs = [
        ProofResponse(**proof)
        for proof in _PROOF_STORE.values()
        if proof["checkin_id"] == checkin_id
    ]
    return sorted(proofs, key=lambda p: p.created_at)


def list_step_proofs(checkin_id: str, step_id: str) -> list[ProofResponse]:
    proofs = [
        ProofResponse(**proof)
        for proof in _PROOF_STORE.values()
        if proof["checkin_id"] == checkin_id and proof["step_id"] == step_id
    ]
    return sorted(proofs, key=lambda p: p.created_at)


def update_proof_status(proof_id: str, status: ProofStatus) -> ProofResponse:
    proof = _PROOF_STORE.get(proof_id)
    if not proof:
        raise ValueError("Proof not found.")

    proof["status"] = status
    proof["updated_at"] = datetime.now(timezone.utc)

    return ProofResponse(**proof)