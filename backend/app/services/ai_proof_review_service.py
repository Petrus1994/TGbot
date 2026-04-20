from __future__ import annotations

from typing import Tuple
import re

from app.models.proof import ProofStatus


POSITIVE_MARKERS = {
    "done",
    "completed",
    "finished",
    "i did it",
    "done today",
    "completed today",
    "finished today",
    "read",
    "studied",
    "trained",
    "worked out",
    "walked",
    "ran",
    "wrote",
    "built",
    "coded",
    "practiced",
    "learned",
    "reviewed",
    "planned",
    "прочитал",
    "сделал",
    "выполнил",
    "выполнено",
    "закончил",
    "завершил",
    "потренировался",
    "тренировка",
    "позанимался",
    "изучил",
    "написал",
    "сделано",
    "готово",
    "прочитано",
}

WEAK_MARKERS = {
    "ok",
    "done?",
    "maybe",
    "later",
    "tomorrow",
    "потом",
    "позже",
    "наверное",
    "может быть",
    "завтра",
}

READING_MARKERS = {
    "page",
    "pages",
    "chapter",
    "book",
    "read",
    "reading",
    "стр",
    "страниц",
    "страницы",
    "страница",
    "глава",
    "книга",
    "прочитал",
    "читал",
}

WORKOUT_MARKERS = {
    "workout",
    "training",
    "exercise",
    "squat",
    "push-up",
    "pushups",
    "pull-up",
    "run",
    "running",
    "gym",
    "cardio",
    "sets",
    "reps",
    "тренировка",
    "зал",
    "кардио",
    "подход",
    "повтор",
    "присед",
    "бег",
    "упражнение",
}

WRITING_MARKERS = {
    "wrote",
    "draft",
    "article",
    "essay",
    "post",
    "journal",
    "note",
    "written",
    "написал",
    "текст",
    "статья",
    "заметка",
    "черновик",
    "пост",
}

CODING_MARKERS = {
    "code",
    "coding",
    "commit",
    "repo",
    "repository",
    "bug",
    "fix",
    "implemented",
    "script",
    "backend",
    "frontend",
    "python",
    "код",
    "коммит",
    "репо",
    "исправил",
    "сделал фичу",
    "скрипт",
    "реализовал",
}

PLANNING_MARKERS = {
    "plan",
    "planned",
    "review",
    "reviewed",
    "reflection",
    "reflected",
    "analyzed",
    "summary",
    "next steps",
    "план",
    "запланировал",
    "разобрал",
    "рефлексия",
    "анализ",
    "итог",
    "вывод",
}

PHOTO_LIKE_WORDS = {
    "photo",
    "picture",
    "image",
    "screenshot",
    "screen",
    "attached",
    "attachment",
    "see attachment",
    "см. фото",
    "фото",
    "скрин",
    "скриншот",
    "вложил",
    "прикрепил",
}

ATTACHMENT_PROOF_TYPES = {"photo", "screenshot", "file", "video"}


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip().lower()


def _contains_any(text: str, markers: set[str]) -> bool:
    return any(marker in text for marker in markers)


def _extract_numbers(text: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", text)]


def _looks_meaningful_text(text: str) -> bool:
    if len(text.strip()) < 12:
        return False
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9]+", text)
    return len(words) >= 3


def _task_context(task_title: str | None, task_description: str | None) -> str:
    return _normalize_text(f"{task_title or ''} {task_description or ''}")


def _proof_context(proof_text: str | None, proof_caption: str | None) -> str:
    return _normalize_text(f"{proof_text or ''} {proof_caption or ''}")


def _is_reading_task(task_text: str) -> bool:
    return _contains_any(task_text, READING_MARKERS)


def _is_workout_task(task_text: str) -> bool:
    return _contains_any(task_text, WORKOUT_MARKERS)


def _is_writing_task(task_text: str) -> bool:
    return _contains_any(task_text, WRITING_MARKERS)


def _is_coding_task(task_text: str) -> bool:
    return _contains_any(task_text, CODING_MARKERS)


def _is_planning_task(task_text: str) -> bool:
    return _contains_any(task_text, PLANNING_MARKERS)


def _has_attachment(
    *,
    proof_type: str | None,
    telegram_file_id: str | None,
    mime_type: str | None,
    filename: str | None,
) -> bool:
    normalized_type = _normalize_text(proof_type)
    return bool(
        telegram_file_id
        or mime_type
        or filename
        or normalized_type in ATTACHMENT_PROOF_TYPES
    )


def _evaluate_attachment_only(
    *,
    task_text: str,
    proof_type: str | None,
) -> tuple[ProofStatus, str] | None:
    normalized_type = _normalize_text(proof_type)

    if normalized_type == "photo":
        if _is_reading_task(task_text):
            return (
                ProofStatus.accepted,
                "Photo proof accepted: it is enough for this reading task.",
            )
        if _is_workout_task(task_text):
            return (
                ProofStatus.accepted,
                "Photo proof accepted: it is enough for this workout task.",
            )
        return (
            ProofStatus.accepted,
            "Photo proof accepted.",
        )

    if normalized_type == "screenshot":
        if _is_coding_task(task_text):
            return (
                ProofStatus.accepted,
                "Screenshot proof accepted for coding progress.",
            )
        if _is_writing_task(task_text):
            return (
                ProofStatus.accepted,
                "Screenshot proof accepted for writing progress.",
            )
        return (
            ProofStatus.accepted,
            "Screenshot proof accepted.",
        )

    if normalized_type in {"file", "video"}:
        return (
            ProofStatus.accepted,
            "Attached file proof accepted.",
        )

    return None


def _evaluate_reading_proof(
    proof_text: str,
    has_attachment: bool,
) -> tuple[ProofStatus, str] | None:
    numbers = _extract_numbers(proof_text)

    if len(numbers) >= 2:
        return (
            ProofStatus.accepted,
            "Reading progress confirmed by page range.",
        )

    if has_attachment or _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Reading proof accepted by photo or screenshot.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Reading progress described clearly enough.",
        )

    return None


def _evaluate_workout_proof(
    proof_text: str,
    has_attachment: bool,
) -> tuple[ProofStatus, str] | None:
    numbers = _extract_numbers(proof_text)

    if has_attachment or _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Workout proof accepted by photo or attachment.",
        )

    if len(numbers) >= 1 and _contains_any(proof_text, WORKOUT_MARKERS | POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Workout details detected in proof.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Workout completion described clearly enough.",
        )

    return None


def _evaluate_writing_proof(
    proof_text: str,
    has_attachment: bool,
) -> tuple[ProofStatus, str] | None:
    if has_attachment or _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Writing proof accepted by screenshot or attachment.",
        )

    if _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Writing result described clearly enough.",
        )

    return None


def _evaluate_coding_proof(
    proof_text: str,
    has_attachment: bool,
) -> tuple[ProofStatus, str] | None:
    if has_attachment or _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Coding proof accepted by screenshot or attachment.",
        )

    if _contains_any(proof_text, CODING_MARKERS) and _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Coding progress described clearly enough.",
        )

    return None


def _evaluate_planning_proof(
    proof_text: str,
) -> tuple[ProofStatus, str] | None:
    if _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Planning result described clearly enough.",
        )

    return None


def _generic_acceptance(
    proof_text: str,
    has_attachment: bool,
) -> tuple[ProofStatus, str] | None:
    if has_attachment or _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Attachment-based proof accepted.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Completion described clearly enough.",
        )

    return None


def _run_review_core(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
    proof_type: str | None,
    telegram_file_id: str | None,
    mime_type: str | None,
    filename: str | None,
) -> Tuple[ProofStatus, str]:
    task_text = _task_context(task_title, task_description)
    proof_text_norm = _proof_context(proof_text, proof_caption)
    has_attachment = _has_attachment(
        proof_type=proof_type,
        telegram_file_id=telegram_file_id,
        mime_type=mime_type,
        filename=filename,
    )

    if not proof_text_norm.strip() and not has_attachment:
        return (
            ProofStatus.needs_more,
            "Proof is missing. Add a short explanation or attach evidence.",
        )

    if not proof_text_norm.strip() and has_attachment:
        attachment_result = _evaluate_attachment_only(
            task_text=task_text,
            proof_type=proof_type,
        )
        if attachment_result:
            return attachment_result

        return (
            ProofStatus.accepted,
            "Attachment received and accepted as proof.",
        )

    if _contains_any(proof_text_norm, WEAK_MARKERS) and len(proof_text_norm) < 20 and not has_attachment:
        return (
            ProofStatus.needs_more,
            "Proof is too vague. Add a clearer result or simple evidence.",
        )

    if len(proof_text_norm) < 6 and not has_attachment:
        return (
            ProofStatus.needs_more,
            "Proof is too short. Add a few words about what exactly was completed.",
        )

    if _is_reading_task(task_text):
        result = _evaluate_reading_proof(proof_text_norm, has_attachment)
        if result:
            return result

    if _is_workout_task(task_text):
        result = _evaluate_workout_proof(proof_text_norm, has_attachment)
        if result:
            return result

    if _is_writing_task(task_text):
        result = _evaluate_writing_proof(proof_text_norm, has_attachment)
        if result:
            return result

    if _is_coding_task(task_text):
        result = _evaluate_coding_proof(proof_text_norm, has_attachment)
        if result:
            return result

    if _is_planning_task(task_text):
        result = _evaluate_planning_proof(proof_text_norm)
        if result:
            return result

    generic_result = _generic_acceptance(proof_text_norm, has_attachment)
    if generic_result:
        return generic_result

    if has_attachment:
        return (
            ProofStatus.needs_more,
            "Attachment received, but add a short note with the concrete result.",
        )

    if len(proof_text_norm) >= 20:
        return (
            ProofStatus.needs_more,
            "Proof is partly clear, but add a bit more concrete result or simple evidence.",
        )

    return (
        ProofStatus.needs_more,
        "Proof is unclear. Add a short concrete result, screenshot, or photo.",
    )


async def run_ai_proof_review(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
    proof_type: str | None = None,
    telegram_file_id: str | None = None,
    mime_type: str | None = None,
    filename: str | None = None,
) -> Tuple[ProofStatus, str]:
    return _run_review_core(
        task_title=task_title,
        task_description=task_description,
        proof_text=proof_text,
        proof_caption=proof_caption,
        proof_type=proof_type,
        telegram_file_id=telegram_file_id,
        mime_type=mime_type,
        filename=filename,
    )


def run_ai_proof_review_sync(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
    proof_type: str | None = None,
    telegram_file_id: str | None = None,
    mime_type: str | None = None,
    filename: str | None = None,
) -> Tuple[ProofStatus, str]:
    return _run_review_core(
        task_title=task_title,
        task_description=task_description,
        proof_text=proof_text,
        proof_caption=proof_caption,
        proof_type=proof_type,
        telegram_file_id=telegram_file_id,
        mime_type=mime_type,
        filename=filename,
    )