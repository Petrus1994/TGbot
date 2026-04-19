from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from app.db import engine
from app.models.proof import ProofStatus
from app.schemas.proof import (
    CreateProofRequest,
    ProofResponse,
    ReviewProofRequest,
)

# 🔥 AI review
from app.services.ai_proof_review_service import run_ai_proof_review_sync


ACCEPTED_LIKE_PROOF_STATUSES = {
    ProofStatus.accepted.value,
}


def _map_row_to_proof_response(row) -> ProofResponse:
    return ProofResponse(
        proof_id=str(row["id"]),
        goal_id=str(row["goal_id"]),
        daily_plan_id=str(row["daily_plan_id"]),
        daily_task_id=str(row["daily_task_id"]),
        proof_type=row["proof_type"],
        telegram_file_id=row["telegram_file_id"],
        file_unique_id=row["file_unique_id"],
        mime_type=row["mime_type"],
        filename=row["filename"],
        caption=row["caption"],
        text=row["text"],
        status=row["status"],
        review_message=row["review_message"],
        submitted_at=row["submitted_at"],
        reviewed_at=row["reviewed_at"],
        created_at=row["created_at"],
    )


def create_proof_for_task(task_id: str, payload: CreateProofRequest) -> ProofResponse | None:
    with engine.begin() as conn:
        task_row = conn.execute(
            text(
                """
                SELECT id, goal_id, daily_plan_id, title, description
                FROM daily_tasks
                WHERE id = :task_id
                LIMIT 1
                """
            ),
            {"task_id": task_id},
        ).mappings().first()

        if not task_row:
            return None

        row = conn.execute(
            text(
                """
                INSERT INTO proofs (
                    goal_id,
                    daily_plan_id,
                    daily_task_id,
                    proof_type,
                    telegram_file_id,
                    file_unique_id,
                    mime_type,
                    filename,
                    caption,
                    text,
                    status,
                    submitted_at
                )
                VALUES (
                    :goal_id,
                    :daily_plan_id,
                    :daily_task_id,
                    :proof_type,
                    :telegram_file_id,
                    :file_unique_id,
                    :mime_type,
                    :filename,
                    :caption,
                    :text,
                    :status,
                    :submitted_at
                )
                RETURNING *
                """
            ),
            {
                "goal_id": str(task_row["goal_id"]),
                "daily_plan_id": str(task_row["daily_plan_id"]),
                "daily_task_id": task_id,
                "proof_type": payload.proof_type.value,
                "telegram_file_id": payload.telegram_file_id,
                "file_unique_id": payload.file_unique_id,
                "mime_type": payload.mime_type,
                "filename": payload.filename,
                "caption": payload.caption,
                "text": payload.text,
                "status": ProofStatus.uploaded.value,
                "submitted_at": datetime.now(timezone.utc),
            },
        ).mappings().one()

    proof = _map_row_to_proof_response(row)

    # 🔥 AI REVIEW (фикс)
    try:
        review_status, review_message = run_ai_proof_review_sync(
            task_title=task_row.get("title"),
            task_description=task_row.get("description"),
            proof_text=proof.text,
            proof_caption=proof.caption,
        )

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE proofs
                    SET
                        status = :status,
                        review_message = :review_message,
                        reviewed_at = :reviewed_at,
                        updated_at = NOW()
                    WHERE id = :proof_id
                    """
                ),
                {
                    "proof_id": proof.proof_id,
                    "status": review_status.value,
                    "review_message": review_message,
                    "reviewed_at": datetime.now(timezone.utc),
                },
            )

        # обновляем proof перед возвратом
        with engine.begin() as conn:
            updated_row = conn.execute(
                text("SELECT * FROM proofs WHERE id = :proof_id"),
                {"proof_id": proof.proof_id},
            ).mappings().one()

        return _map_row_to_proof_response(updated_row)

    except Exception as e:
        print(f"❌ AI PROOF REVIEW FAILED: {e}")

    return proof


def list_task_proofs(task_id: str) -> list[ProofResponse]:
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT *
                FROM proofs
                WHERE daily_task_id = :task_id
                ORDER BY created_at ASC
                """
            ),
            {"task_id": task_id},
        ).mappings().all()

        return [_map_row_to_proof_response(row) for row in rows]


def review_proof(proof_id: str, payload: ReviewProofRequest) -> ProofResponse | None:
    with engine.begin() as conn:
        existing = conn.execute(
            text(
                "SELECT id FROM proofs WHERE id = :proof_id LIMIT 1"
            ),
            {"proof_id": proof_id},
        ).mappings().first()

        if not existing:
            return None

        reviewed_at = (
            datetime.now(timezone.utc)
            if payload.status in {
                ProofStatus.accepted,
                ProofStatus.rejected,
                ProofStatus.needs_more,
            }
            else None
        )

        row = conn.execute(
            text(
                """
                UPDATE proofs
                SET
                    status = :status,
                    review_message = :review_message,
                    reviewed_at = :reviewed_at,
                    updated_at = NOW()
                WHERE id = :proof_id
                RETURNING *
                """
            ),
            {
                "proof_id": proof_id,
                "status": payload.status.value,
                "review_message": payload.review_message,
                "reviewed_at": reviewed_at,
            },
        ).mappings().one()

        return _map_row_to_proof_response(row)


def task_has_required_proof(task_id: str) -> bool:
    return task_has_accepted_required_proof(task_id)


def task_has_accepted_required_proof(task_id: str) -> bool:
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                SELECT EXISTS(
                    SELECT 1
                    FROM proofs
                    WHERE daily_task_id = :task_id
                      AND status = 'accepted'
                )
                """
            ),
            {"task_id": task_id},
        ).scalar()

        return bool(row)


def daily_plan_all_required_proofs_present(daily_plan_id: str) -> bool:
    with engine.begin() as conn:
        stats = conn.execute(
            text(
                """
                SELECT
                    COUNT(*) FILTER (WHERE proof_required = TRUE) AS required_tasks,
                    COUNT(*) FILTER (
                        WHERE proof_required = TRUE
                        AND EXISTS (
                            SELECT 1 FROM proofs p
                            WHERE p.daily_task_id = daily_tasks.id
                              AND p.status = 'accepted'
                        )
                    ) AS satisfied_required_tasks
                FROM daily_tasks
                WHERE daily_plan_id = :daily_plan_id
                """
            ),
            {"daily_plan_id": daily_plan_id},
        ).mappings().one()

        return int(stats["required_tasks"] or 0) == int(stats["satisfied_required_tasks"] or 0)