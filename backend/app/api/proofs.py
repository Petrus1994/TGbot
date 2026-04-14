from fastapi import APIRouter, HTTPException, status

from app.schemas.proof import CreateProofRequest, ProofResponse, ReviewProofRequest
from app.services.proof_service import (
    create_proof_for_task,
    get_daily_plan_proof_summary,
    list_task_proofs,
    review_proof,
)

router = APIRouter(tags=["proofs"])


@router.post(
    "/daily-tasks/{task_id}/proofs",
    response_model=ProofResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task_proof(task_id: str, payload: CreateProofRequest):
    proof = create_proof_for_task(task_id, payload)
    if not proof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="daily_task_not_found",
        )
    return proof


@router.get(
    "/daily-tasks/{task_id}/proofs",
    response_model=list[ProofResponse],
)
def get_task_proofs(task_id: str):
    return list_task_proofs(task_id)


@router.post(
    "/proofs/{proof_id}/review",
    response_model=ProofResponse,
)
def review_task_proof(proof_id: str, payload: ReviewProofRequest):
    proof = review_proof(proof_id, payload)
    if not proof:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="proof_not_found",
        )
    return proof


@router.get(
    "/daily-plans/{daily_plan_id}/proofs-summary",
    status_code=status.HTTP_200_OK,
)
def get_daily_plan_proofs_summary(daily_plan_id: str):
    return get_daily_plan_proof_summary(daily_plan_id)