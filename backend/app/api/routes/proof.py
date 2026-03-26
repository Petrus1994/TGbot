from fastapi import APIRouter, HTTPException, status

from app.schemas.proof import CreateProofRequest, ProofResponse, UpdateProofStatusRequest
from app.services.proof_service import (
    create_proof,
    list_checkin_proofs,
    list_step_proofs,
    update_proof_status,
)

router = APIRouter(tags=["proofs"])


@router.post(
    "/checkins/{checkin_id}/steps/{step_id}/proofs",
    response_model=ProofResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_proof_endpoint(checkin_id: str, step_id: str, payload: CreateProofRequest):
    try:
        return create_proof(checkin_id, step_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/checkins/{checkin_id}/proofs",
    response_model=list[ProofResponse],
)
def list_checkin_proofs_endpoint(checkin_id: str):
    return list_checkin_proofs(checkin_id)


@router.get(
    "/checkins/{checkin_id}/steps/{step_id}/proofs",
    response_model=list[ProofResponse],
)
def list_step_proofs_endpoint(checkin_id: str, step_id: str):
    return list_step_proofs(checkin_id, step_id)


@router.post(
    "/proofs/{proof_id}/status",
    response_model=ProofResponse,
)
def update_proof_status_endpoint(proof_id: str, payload: UpdateProofStatusRequest):
    try:
        return update_proof_status(proof_id, payload.status)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e