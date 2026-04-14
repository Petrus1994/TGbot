from __future__ import annotations

import re
from typing import Tuple

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
    "see attachment",
    "см. фото",
    "фото",
    "скрин",
    "скриншот",
    "вложил",
    "прикрепил",
}


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


def _evaluate_reading_proof(proof_text: str) -> tuple[ProofStatus, str] | None:
    numbers = _extract_numbers(proof_text)

    if len(numbers) >= 2:
        return (
            ProofStatus.accepted,
            "Proof looks valid: reading progress with page range is provided.",
        )

    if _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: a photo or screenshot of reading progress is mentioned.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Proof looks reasonable: reading progress is described clearly.",
        )

    return None


def _evaluate_workout_proof(proof_text: str) -> tuple[ProofStatus, str] | None:
    numbers = _extract_numbers(proof_text)

    if _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: workout context photo or screenshot is mentioned.",
        )

    if len(numbers) >= 1 and _contains_any(proof_text, WORKOUT_MARKERS | POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: workout details with repetitions, duration, or exercise are provided.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Proof looks reasonable: workout completion is described clearly.",
        )

    return None


def _evaluate_writing_proof(proof_text: str) -> tuple[ProofStatus, str] | None:
    if _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: screenshot or image of the written result is mentioned.",
        )

    if _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Proof looks valid: the written result is described with enough detail.",
        )

    return None


def _evaluate_coding_proof(proof_text: str) -> tuple[ProofStatus, str] | None:
    if _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: screenshot or attachment for coding progress is mentioned.",
        )

    if _contains_any(proof_text, CODING_MARKERS) and _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Proof looks valid: coding progress is described clearly.",
        )

    return None


def _evaluate_planning_proof(proof_text: str) -> tuple[ProofStatus, str] | None:
    if _looks_meaningful_text(proof_text):
        return (
            ProofStatus.accepted,
            "Proof looks valid: planning or reflection result is described clearly.",
        )

    return None


def _generic_acceptance(proof_text: str) -> tuple[ProofStatus, str] | None:
    if _contains_any(proof_text, PHOTO_LIKE_WORDS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: attachment, photo, or screenshot is referenced.",
        )

    if _looks_meaningful_text(proof_text) and _contains_any(proof_text, POSITIVE_MARKERS):
        return (
            ProofStatus.accepted,
            "Proof looks valid: completion is described clearly enough.",
        )

    return None


async def run_ai_proof_review(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
) -> Tuple[ProofStatus, str]:
    """
    Rule-based AI-like proof review.
    Сигнатура сохранена, чтобы ничего не ломать.
    """

    task_text = _task_context(task_title, task_description)
    proof_text_norm = _proof_context(proof_text, proof_caption)

    if not proof_text_norm.strip():
        return (
            ProofStatus.needs_more,
            "Proof is missing. Add a short explanation or attach evidence.",
        )

    if _contains_any(proof_text_norm, WEAK_MARKERS) and len(proof_text_norm) < 20:
        return (
            ProofStatus.needs_more,
            "Proof is too vague. Add a clearer result or attach simple evidence.",
        )

    if len(proof_text_norm) < 6:
        return (
            ProofStatus.needs_more,
            "Proof is too short. Add a few words about what exactly was completed.",
        )

    if _is_reading_task(task_text):
        result = _evaluate_reading_proof(proof_text_norm)
        if result:
            return result

    if _is_workout_task(task_text):
        result = _evaluate_workout_proof(proof_text_norm)
        if result:
            return result

    if _is_writing_task(task_text):
        result = _evaluate_writing_proof(proof_text_norm)
        if result:
            return result

    if _is_coding_task(task_text):
        result = _evaluate_coding_proof(proof_text_norm)
        if result:
            return result

    if _is_planning_task(task_text):
        result = _evaluate_planning_proof(proof_text_norm)
        if result:
            return result

    generic_result = _generic_acceptance(proof_text_norm)
    if generic_result:
        return generic_result

    if len(proof_text_norm) >= 20:
        return (
            ProofStatus.needs_more,
            "Proof is partly clear, but add a bit more concrete result or simple evidence.",
        )

    return (
        ProofStatus.needs_more,
        "Proof is unclear. Add a short concrete result, screenshot, or photo.",
    )