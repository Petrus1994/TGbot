from __future__ import annotations

import re
import asyncio
from typing import Tuple

from app.models.proof import ProofStatus


POSITIVE_MARKERS = {
    "done", "completed", "finished", "i did it",
    "done today", "completed today", "finished today",
    "read", "studied", "trained", "worked out", "walked", "ran",
    "wrote", "built", "coded", "practiced", "learned",
    "reviewed", "planned",
    "прочитал", "сделал", "выполнил", "выполнено",
    "закончил", "завершил", "потренировался",
    "тренировка", "позанимался", "изучил",
    "написал", "сделано", "готово", "прочитано",
}

WEAK_MARKERS = {
    "ok", "done?", "maybe", "later", "tomorrow",
    "потом", "позже", "наверное", "может быть", "завтра",
}

READING_MARKERS = {
    "page", "pages", "chapter", "book", "read", "reading",
    "стр", "страниц", "страницы", "страница",
    "глава", "книга", "прочитал", "читал",
}

WORKOUT_MARKERS = {
    "workout", "training", "exercise", "squat", "push-up",
    "run", "running", "gym", "cardio", "sets", "reps",
    "тренировка", "зал", "кардио", "подход",
    "повтор", "присед", "бег", "упражнение",
}

WRITING_MARKERS = {
    "wrote", "draft", "article", "essay", "post",
    "journal", "note", "written",
    "написал", "текст", "статья", "заметка",
    "черновик", "пост",
}

CODING_MARKERS = {
    "code", "coding", "commit", "repo",
    "bug", "fix", "implemented", "script",
    "backend", "frontend", "python",
    "код", "коммит", "репо",
    "исправил", "реализовал",
}

PLANNING_MARKERS = {
    "plan", "planned", "review", "reflection",
    "analyzed", "summary", "next steps",
    "план", "разбор", "рефлексия",
    "анализ", "итог", "вывод",
}

PHOTO_LIKE_WORDS = {
    "photo", "picture", "image", "screenshot",
    "screen", "attached", "см. фото",
    "фото", "скрин", "прикрепил",
}


# ------------------ helpers ------------------

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


# ------------------ evaluators ------------------

def _evaluate_reading_proof(text: str):
    if len(_extract_numbers(text)) >= 2:
        return ProofStatus.accepted, "Reading progress confirmed (pages/range)."
    if _contains_any(text, PHOTO_LIKE_WORDS):
        return ProofStatus.accepted, "Reading proof via photo/screenshot."
    return None


def _evaluate_workout_proof(text: str):
    if _contains_any(text, PHOTO_LIKE_WORDS):
        return ProofStatus.accepted, "Workout proof via photo."
    if _extract_numbers(text):
        return ProofStatus.accepted, "Workout metrics detected."
    return None


def _evaluate_generic(text: str):
    if _contains_any(text, PHOTO_LIKE_WORDS):
        return ProofStatus.accepted, "Attachment referenced."
    if _looks_meaningful_text(text) and _contains_any(text, POSITIVE_MARKERS):
        return ProofStatus.accepted, "Clear completion description."
    return None


# ------------------ main ------------------

async def run_ai_proof_review(
    *,
    task_title: str | None,
    task_description: str | None,
    proof_text: str | None,
    proof_caption: str | None,
) -> Tuple[ProofStatus, str]:

    task_text = _task_context(task_title, task_description)
    proof = _proof_context(proof_text, proof_caption)

    if not proof:
        return ProofStatus.needs_more, "Proof missing."

    if len(proof) < 6:
        return ProofStatus.needs_more, "Too short."

    if _contains_any(proof, WEAK_MARKERS):
        return ProofStatus.needs_more, "Too vague."

    if _contains_any(task_text, READING_MARKERS):
        res = _evaluate_reading_proof(proof)
        if res:
            return res

    if _contains_any(task_text, WORKOUT_MARKERS):
        res = _evaluate_workout_proof(proof)
        if res:
            return res

    res = _evaluate_generic(proof)
    if res:
        return res

    return ProofStatus.needs_more, "Add clearer proof."


# 🔥 sync wrapper (ОБЯЗАТЕЛЬНО)
def run_ai_proof_review_sync(**kwargs):
    return asyncio.run(run_ai_proof_review(**kwargs))