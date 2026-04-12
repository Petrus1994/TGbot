from __future__ import annotations

import copy
from typing import Any

from app.services.ai_profiling_service import AIProfilingService


DEFAULT_QUESTION_BANK = [
    # CORE (обязательные)
    {
        "id": "q1",
        "key": "goal_outcome",
        "text": "Какой конкретный результат ты хочешь получить?",
        "example_answer": "Хочу выйти на доход 3000$ в месяц за 6 месяцев",
        "priority": 100,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q2",
        "key": "current_level",
        "text": "Где ты сейчас относительно этой цели?",
        "example_answer": "Сейчас я только начинаю и пока не получал результатов",
        "priority": 99,
        "question_type": "text",
        "suggested_options": None,
        "allow_free_text": True,
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q3",
        "key": "constraints",
        "text": "Какие у тебя реальные ограничения (время, деньги, энергия)?",
        "example_answer": "Работаю full-time и могу уделять цели только вечерами",
        "priority": 98,
        "question_type": "text",
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q4",
        "key": "time_budget",
        "text": "Сколько времени ты реально готов уделять в неделю?",
        "example_answer": "7-10 часов в неделю",
        "priority": 97,
        "question_type": "choice_or_text",
        "suggested_options": ["<5h", "5-10h", "10-20h", "20h+"],
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q5",
        "key": "main_obstacles",
        "text": "Что обычно мешает тебе доводить такие цели до результата?",
        "example_answer": "Прокрастинация и отсутствие системы",
        "priority": 96,
        "question_type": "text",
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q6",
        "key": "resources",
        "text": "Какие ресурсы у тебя уже есть?",
        "example_answer": "Ноутбук, интернет, доступ к курсам",
        "priority": 95,
        "question_type": "text",
        "required": True,
        "domains": ["generic"],
    },
    {
        "id": "q7",
        "key": "motivation",
        "text": "Почему эта цель реально важна для тебя?",
        "example_answer": "Хочу больше свободы и денег",
        "priority": 94,
        "question_type": "text",
        "required": True,
        "domains": ["generic"],
    },

    # UNIVERSAL DEEP
    {
        "id": "q8",
        "key": "deadline",
        "text": "За какой срок ты хочешь результата?",
        "example_answer": "3-6 месяцев",
        "priority": 90,
        "question_type": "choice_or_text",
        "suggested_options": ["1-3", "3-6", "6-12", "no deadline"],
        "domains": ["generic"],
    },
    {
        "id": "q9",
        "key": "daily_routine",
        "text": "Как сейчас выглядит твой день?",
        "example_answer": "Свободен вечером 2-3 часа",
        "priority": 85,
        "question_type": "text",
        "domains": ["generic"],
    },
    {
        "id": "q10",
        "key": "coach_style",
        "text": "Какой стиль коучинга тебе подходит?",
        "priority": 80,
        "question_type": "choice",
        "suggested_options": ["aggressive", "balanced", "soft"],
        "required": True,
        "domains": ["generic"],
    },

    # FITNESS
    {
        "id": "qf1",
        "key": "body_metrics",
        "text": "Рост / вес / примерный % жира?",
        "priority": 95,
        "domains": ["fitness"],
    },
    {
        "id": "qf2",
        "key": "training_access",
        "text": "Есть ли доступ к залу?",
        "priority": 93,
        "question_type": "choice_or_text",
        "suggested_options": ["gym", "home", "mixed"],
        "domains": ["fitness"],
    },
    {
        "id": "qf3",
        "key": "nutrition_state",
        "text": "Как сейчас выглядит питание?",
        "priority": 92,
        "domains": ["fitness"],
    },

    # MONEY / BUSINESS
    {
        "id": "qb1",
        "key": "current_income",
        "text": "Текущий доход / ситуация?",
        "priority": 95,
        "domains": ["income", "business"],
    },
    {
        "id": "qb2",
        "key": "income_model",
        "text": "Как ты планируешь зарабатывать?",
        "priority": 93,
        "question_type": "choice_or_text",
        "suggested_options": ["job", "clients", "product", "content"],
        "domains": ["income", "business"],
    },
]


class DynamicProfilingService:
    def __init__(self):
        self.ai_service = AIProfilingService()

    async def build_context(self, goal_title: str, goal_description: str | None = None) -> dict:
        goal_type = self._infer_goal_type(goal_title, goal_description)

        questions = self._filter_questions_by_domain(goal_type)

        return {
            "profiling": {
                "mode": "adaptive",
                "goal_type": goal_type,
                "questions": questions,
                "answers": {},
                "asked_question_keys": [],
                "skipped_question_keys": [],
                "follow_up_attempts": {},
                "current_question_key": questions[0]["key"],
                "is_completed": False,
                "questions_total_count": len(questions),
                "questions_answered_count": 0,
                "minimum_required_answers": 6,
            }
        }

    async def select_next_step(
        self,
        goal_title: str,
        goal_description: str | None,
        questions: list[dict],
        answers: dict[str, str],
        asked_question_keys: list[str] | None = None,
        skipped_question_keys: list[str] | None = None,
    ) -> dict:

        asked_question_keys = asked_question_keys or []
        skipped_question_keys = skipped_question_keys or []

        remaining = [
            q for q in questions
            if q["key"] not in answers
            and q["key"] not in asked_question_keys
            and q["key"] not in skipped_question_keys
        ]

        if not remaining:
            return {"is_completed": True}

        # приоритет обязательных
        required_missing = [
            q for q in remaining if q.get("required")
        ]

        if required_missing:
            next_q = sorted(required_missing, key=lambda x: x["priority"], reverse=True)[0]
            return {"is_completed": False, "next_question_key": next_q["key"]}

        # AI decision
        try:
            result = await self.ai_service.select_next_question(
                goal_title=goal_title,
                goal_description=goal_description,
                answers=answers,
                candidate_questions=remaining,
            )

            if result.get("is_completed"):
                return {"is_completed": True}

            key = result.get("next_question_key")
            if key:
                return {"is_completed": False, "next_question_key": key}

        except Exception:
            pass

        # fallback
        next_q = sorted(remaining, key=lambda x: x["priority"], reverse=True)[0]
        return {"is_completed": False, "next_question_key": next_q["key"]}

    def _filter_questions_by_domain(self, goal_type: str) -> list[dict]:
        questions = []

        for q in copy.deepcopy(DEFAULT_QUESTION_BANK):
            domains = q.get("domains", ["generic"])

            if "generic" in domains or goal_type in domains:
                questions.append(q)

        return sorted(questions, key=lambda x: x["priority"], reverse=True)

    def _infer_goal_type(self, title: str, description: str | None) -> str:
        text = f"{title} {description or ''}".lower()

        if any(x in text for x in ["weight", "fat", "fitness", "muscle", "пресс"]):
            return "fitness"
        if any(x in text for x in ["income", "money", "деньг", "доход"]):
            return "income"
        if any(x in text for x in ["business", "startup", "клиент"]):
            return "business"

        return "generic"