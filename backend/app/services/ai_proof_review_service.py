from __future__ import annotations

from typing import Tuple

from app.models.proof import ProofStatus


async def run_ai_proof_review(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
) -> Tuple[ProofStatus, str]:
    """
    MVP AI review (заглушка).
    Потом сюда подключишь OpenAI / Claude.
    """

    content = (proof_text or "") + " " + (proof_caption or "")
    content = content.lower()

    # 🔥 Простая логика (пока без LLM)

    if not content.strip():
        return (
            ProofStatus.needs_more,
            "No proof content provided. Add details or attach evidence.",
        )

    if len(content) < 10:
        return (
            ProofStatus.needs_more,
            "Proof is too short. Provide more details or evidence.",
        )

    if any(word in content for word in ["done", "completed", "finished"]):
        return (
            ProofStatus.accepted,
            "Proof looks valid. Task accepted.",
        )

    return (
        ProofStatus.needs_more,
        "Unclear proof. Add more explanation or evidence.",
    )