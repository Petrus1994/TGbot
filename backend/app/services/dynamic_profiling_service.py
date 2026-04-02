from __future__ import annotations

from app.services.ai_profiling_service import AIProfilingService


DEFAULT_QUESTION_BANK = [
    {
        "id": "q1",
        "key": "goal_outcome",
        "text": "Что именно ты хочешь получить в итоге?",
        "example_answer": "Хочу выйти на доход 3000$ в месяц за 6 месяцев",
        "priority": 100,
    },
    {
        "id": "q2",
        "key": "current_level",
        "text": "Где ты сейчас относительно этой цели?",
        "example_answer": "Сейчас я только начинаю и пока не получал результатов",
        "priority": 95,
    },
    {
        "id": "q3",
        "key": "deadline",
        "text": "За какой срок ты хочешь этого достичь?",
        "example_answer": "Хочу добиться этого за 4 месяца",
        "priority": 90,
    },
    {
        "id": "q4",
        "key": "resources",
        "text": "Какие у тебя уже есть ресурсы для этой цели?",
        "example_answer": "Есть ноутбук, интернет, базовые знания и доступ к курсу",
        "priority": 80,
    },
    {
        "id": "q5",
        "key": "constraints",
        "text": "Какие у тебя есть ограничения?",
        "example_answer": "Работаю full-time и могу уделять цели только вечерами",
        "priority": 85,
    },
    {
        "id": "q6",
        "key": "past_attempts",
        "text": "Ты уже пытался достичь этого раньше?",
        "example_answer": "Да, начинал дважды, но бросал через пару недель",
        "priority": 70,
    },
    {
        "id": "q7",
        "key": "obstacles",
        "text": "Что обычно тебе мешает двигаться к таким целям?",
        "example_answer": "Прокрастинация, хаос в расписании и быстро теряю фокус",
        "priority": 88,
    },
    {
        "id": "q8",
        "key": "motivation",
        "text": "Почему эта цель для тебя важна?",
        "example_answer": "Хочу больше свободы, денег и уверенности в себе",
        "priority": 75,
    },
    {
        "id": "q9",
        "key": "daily_routine",
        "text": "Как обычно выглядит твой день или неделя?",
        "example_answer": "По будням свободен с 19:00 до 22:00, в выходные больше времени",
        "priority": 65,
    },
    {
        "id": "q10",
        "key": "time_budget",
        "text": "Сколько времени ты реально готов уделять этой цели?",
        "example_answer": "1 час в день по будням и 3 часа в выходные",
        "priority": 92,
    },
    {
        "id": "q11",
        "key": "coach_style",
        "text": "Какой стиль коучинга тебе подходит?",
        "example_answer": "Нужен прямой и требовательный стиль, без лишней мягкости",
        "priority": 60,
    },
]


class DynamicProfilingService:
    def __init__(self):
        self.ai_service = AIProfilingService()

    async def build_context(self, goal_title: str, goal_description: str | None = None) -> dict:
        """
        Пока создаём baseline context.
        Позже сюда можно вернуть AI-generated bank/questions.
        """
        questions = list(DEFAULT_QUESTION_BANK)

        return {
            "profiling": {
                "mode": "adaptive",
                "goal_analysis": {
                    "goal_type": "custom",
                    "difficulty": "medium",
                    "time_horizon": None,
                },
                "questions": questions,
                "answers": {},
                "asked_question_keys": [],
                "skipped_question_keys": [],
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

        remaining_questions = [
            q
            for q in questions
            if q.get("key") not in answers
            and q.get("key") not in asked_question_keys
            and q.get("key") not in skipped_question_keys
        ]

        if not remaining_questions:
            return {
                "is_completed": True,
                "next_question_key": None,
                "reason": "No remaining questions",
                "source": "fallback",
            }

        # Если ответов ещё мало — не даём AI завершить profiling слишком рано
        minimum_required_answers = 6
        force_continue = len(answers) < minimum_required_answers

        try:
            result = await self.ai_service.select_next_question(
                goal_title=goal_title,
                goal_description=goal_description,
                answers=answers,
                candidate_questions=remaining_questions,
            )

            ai_is_completed = bool(result.get("is_completed", False))
            next_question_key = result.get("next_question_key")
            reason = str(result.get("reason") or "")

            if force_continue and ai_is_completed:
                ai_is_completed = False

            if ai_is_completed:
                return {
                    "is_completed": True,
                    "next_question_key": None,
                    "reason": reason or "AI decided profiling is sufficient",
                    "source": "ai",
                }

            if next_question_key:
                matched = next(
                    (q for q in remaining_questions if q.get("key") == next_question_key),
                    None,
                )
                if matched:
                    return {
                        "is_completed": False,
                        "next_question_key": matched["key"],
                        "reason": reason or "AI selected next question",
                        "source": "ai",
                    }

        except Exception:
            pass

        fallback_question = self._select_fallback_question(remaining_questions)

        return {
            "is_completed": False,
            "next_question_key": fallback_question["key"],
            "reason": "Fallback priority-based selection",
            "source": "fallback",
        }

    def _select_fallback_question(self, remaining_questions: list[dict]) -> dict:
        return sorted(
            remaining_questions,
            key=lambda q: int(q.get("priority", 0)),
            reverse=True,
        )[0]