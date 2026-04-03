from __future__ import annotations

import re

from app.services.ai_profiling_service import AIProfilingService


UNCERTAIN_ANSWER_PATTERNS = {
    "не знаю",
    "хз",
    "без понятия",
    "не уверен",
    "сложно сказать",
    "примерно",
    "как получится",
    "посмотрим",
    "неважно",
    "any",
    "idk",
    "not sure",
    "maybe",
}


class ProfilingQualityService:
    def __init__(self):
        self.ai_service = AIProfilingService()

    async def evaluate_answer(
        self,
        goal_title: str,
        goal_description: str | None,
        question: dict,
        answer: str,
        answers: dict[str, str],
    ) -> dict:
        cleaned_answer = (answer or "").strip()
        question_key = str(question.get("key") or "").strip()

        if not cleaned_answer:
            return self._fallback_result(
                accepted=False,
                reason="empty_answer",
                missing_info="Answer is empty",
                feedback_message="Ответ пустой.",
                follow_up_question="Ответь на вопрос чуть подробнее.",
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question_key),
                source="rule_based",
            )

        if self._looks_uncertain(cleaned_answer):
            return self._fallback_result(
                accepted=False,
                reason="uncertain_answer",
                missing_info="The answer is too uncertain",
                feedback_message=self._build_uncertain_feedback(question_key),
                follow_up_question=self._build_uncertain_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question_key),
                source="rule_based",
            )

        if question_key == "coach_style":
            normalized = cleaned_answer.lower()
            allowed = {"aggressive", "balanced", "soft"}
            if normalized in allowed:
                return self._fallback_result(
                    accepted=True,
                    reason="coach_style_selected",
                    missing_info=None,
                    feedback_message=None,
                    follow_up_question=None,
                    example_answer=None,
                    suggested_options=["aggressive", "balanced", "soft"],
                    source="rule_based",
                )

            return self._fallback_result(
                accepted=False,
                reason="invalid_coach_style",
                missing_info="Expected one of aggressive, balanced, soft",
                feedback_message="Для стиля коучинга лучше выбрать один из готовых вариантов.",
                follow_up_question="Выбери один вариант: aggressive, balanced или soft.",
                example_answer=None,
                suggested_options=["aggressive", "balanced", "soft"],
                source="rule_based",
            )

        if len(cleaned_answer) < 8:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Answer is too short",
                feedback_message=self._build_short_feedback(question_key),
                follow_up_question=self._build_short_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question_key),
                source="rule_based",
            )

        try:
            result = await self.ai_service.judge_answer(
                goal_title=goal_title,
                goal_description=goal_description,
                question=question,
                user_answer=cleaned_answer,
                answers=answers,
            )
            return self._normalize_ai_result(result, question)
        except Exception:
            return self._rule_based_evaluation(question=question, answer=cleaned_answer)

    def _normalize_ai_result(self, result: dict, question: dict) -> dict:
        accepted = bool(result.get("accepted", False))
        question_key = str(question.get("key") or "").strip()

        raw_example = self._nullable_str(result.get("example_answer"))
        fallback_example = self._safe_example(question.get("example_answer"))
        example_answer = self._choose_example(raw_example, fallback_example, question_key)

        suggested_options = self._normalize_options(
            result.get("suggested_options"),
            fallback=self._get_suggested_options(question_key),
        )

        feedback_message = self._nullable_str(result.get("feedback_message"))
        if not feedback_message and not accepted:
            feedback_message = self._build_generic_feedback(question_key)

        follow_up_question = self._nullable_str(result.get("follow_up_question"))
        if not follow_up_question and not accepted:
            follow_up_question = self._build_short_follow_up(question_key)

        return {
            "accepted": accepted,
            "reason": str(result.get("reason") or ("accepted" if accepted else "insufficient_detail")),
            "missing_info": self._nullable_str(result.get("missing_info")),
            "feedback_message": feedback_message,
            "follow_up_question": follow_up_question,
            "example_answer": example_answer,
            "suggested_options": suggested_options,
            "source": "ai",
        }

    def _rule_based_evaluation(self, question: dict, answer: str) -> dict:
        text = answer.strip()
        words = text.split()
        question_key = str(question.get("key") or "").strip()

        if len(words) < 3:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Not enough detail",
                feedback_message=self._build_short_feedback(question_key),
                follow_up_question=self._build_short_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question_key),
                source="rule_based",
            )

        if question_key in {"time_budget", "constraints", "resources", "deadline", "motivation"} and len(text) < 15:
            return self._fallback_result(
                accepted=False,
                reason="not_specific_enough",
                missing_info="Need more practical detail",
                feedback_message=self._build_generic_feedback(question_key),
                follow_up_question=self._build_specific_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question_key),
                source="rule_based",
            )

        return self._fallback_result(
            accepted=True,
            reason="accepted_by_fallback",
            missing_info=None,
            feedback_message=None,
            follow_up_question=None,
            example_answer=None,
            suggested_options=self._get_suggested_options(question_key),
            source="rule_based",
        )

    def _fallback_result(
        self,
        accepted: bool,
        reason: str,
        missing_info: str | None,
        feedback_message: str | None,
        follow_up_question: str | None,
        example_answer: str | None,
        suggested_options: list[str] | None,
        source: str,
    ) -> dict:
        return {
            "accepted": accepted,
            "reason": reason,
            "missing_info": missing_info,
            "feedback_message": feedback_message,
            "follow_up_question": follow_up_question,
            "example_answer": example_answer,
            "suggested_options": suggested_options,
            "source": source,
        }

    def _looks_uncertain(self, answer: str) -> bool:
        normalized = re.sub(r"\s+", " ", answer.strip().lower())
        return normalized in UNCERTAIN_ANSWER_PATTERNS

    def _build_uncertain_feedback(self, question_key: str) -> str:
        if question_key == "deadline":
            return "Нормально ответить примерно. Не нужен идеальный срок."
        if question_key == "time_budget":
            return "Даже примерная оценка времени уже полезна для плана."
        if question_key == "motivation":
            return "Важно понять, зачем тебе эта цель, даже если ответ пока неидеальный."
        return "Можно ответить примерно — этого уже хватит, чтобы двигаться дальше."

    def _build_uncertain_follow_up(self, question_key: str) -> str:
        if question_key == "deadline":
            return "Дай хотя бы ориентир: это скорее 1–3 месяца, 3–6 месяцев или дольше?"
        if question_key == "time_budget":
            return "Сколько времени ты можешь уделять хотя бы примерно: меньше 5 часов, 5–10 часов или 10+ часов в неделю?"
        if question_key == "coach_style":
            return "Выбери один вариант: aggressive, balanced или soft."
        return "Дай хотя бы примерный ориентир или выбери самый близкий вариант."

    def _build_short_feedback(self, question_key: str) -> str:
        feedback_map = {
            "current_level": "Пока непонятно, где ты находишься сейчас относительно цели.",
            "constraints": "Нужно чуть больше конкретики по ограничениям.",
            "resources": "Нужно чуть больше конкретики по ресурсам.",
            "motivation": "Пока неясно, почему эта цель для тебя важна.",
            "deadline": "Пока неясно, в какой срок ты хочешь прийти к результату.",
            "time_budget": "Пока неясно, сколько времени ты реально готов уделять.",
        }
        return feedback_map.get(question_key, "Ответ пока слишком короткий.")

    def _build_short_follow_up(self, question_key: str) -> str:
        follow_up_map = {
            "current_level": "Опиши текущую ситуацию чуть конкретнее: что у тебя уже есть, а чего ещё нет?",
            "constraints": "Какие есть ограничения по времени, деньгам, здоровью или условиям?",
            "resources": "Что у тебя уже есть для этой цели: деньги, навыки, инструменты, связи?",
            "motivation": "Почему эта цель важна именно для тебя? Что изменится, если ты её достигнешь?",
            "deadline": "За какой срок ты хочешь этого добиться хотя бы примерно?",
            "time_budget": "Сколько часов в неделю ты реально готов уделять этой цели?",
        }
        return follow_up_map.get(question_key, "Ответь чуть подробнее и конкретнее.")

    def _build_generic_feedback(self, question_key: str) -> str:
        feedback_map = {
            "current_level": "Ты описал ситуацию слишком общо. Нужна более ясная стартовая точка.",
            "constraints": "Ты назвал ограничения слишком общо. Нужны практические детали.",
            "resources": "Ты перечислил ресурсы слишком расплывчато. Нужны более конкретные опоры.",
            "motivation": "Ты указал мотивацию слишком общо. Нужно понять, что для тебя реально стоит на кону.",
            "deadline": "Срок пока неясный. Для плана нужен хотя бы примерный ориентир.",
            "time_budget": "По времени пока мало конкретики. Это важно для реалистичного плана.",
            "coach_style": "Нужно понять, какой формат коучинга тебе подходит.",
        }
        return feedback_map.get(question_key, "Ответ пока слишком общий.")

    def _build_specific_follow_up(self, question_key: str) -> str:
        follow_up_map = {
            "constraints": "Добавь конкретику: время, деньги, здоровье, работа или другие условия.",
            "resources": "Перечисли реальные ресурсы: деньги, навыки, инструменты, связи, доступ к платформам.",
            "motivation": "Скажи конкретнее: зачем тебе эта цель и что изменится после результата?",
            "deadline": "Укажи хотя бы примерный срок: недели, месяцы или дольше.",
            "time_budget": "Добавь практическую оценку: сколько часов в день или неделю ты готов выделять?",
        }
        return follow_up_map.get(question_key, "Добавь чуть больше конкретики.")

    def _get_suggested_options(self, question_key: str) -> list[str] | None:
        options_map = {
            "coach_style": ["aggressive", "balanced", "soft"],
            "deadline": ["1-3 months", "3-6 months", "6-12 months", "no strict deadline"],
            "time_budget": ["<5 hours/week", "5-10 hours/week", "10+ hours/week"],
        }
        return options_map.get(question_key)

    def _normalize_options(self, value, fallback: list[str] | None = None) -> list[str] | None:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return items or fallback
        return fallback

    def _safe_example(self, value) -> str | None:
        value = self._nullable_str(value)
        if not value:
            return None
        if len(value.split()) < 3:
            return None
        return value

    def _choose_example(
        self,
        ai_example: str | None,
        fallback_example: str | None,
        question_key: str,
    ) -> str | None:
        candidate = self._safe_example(ai_example)
        if candidate and self._example_is_relevant(candidate, question_key):
            return candidate
        if fallback_example and self._example_is_relevant(fallback_example, question_key):
            return fallback_example
        return None

    def _example_is_relevant(self, example: str, question_key: str) -> bool:
        text = example.lower()

        if question_key == "coach_style":
            return any(option in text for option in ["aggressive", "balanced", "soft", "жест", "мяг", "баланс"])
        if question_key == "deadline":
            return any(token in text for token in ["month", "week", "год", "меся", "недел", "срок"])
        if question_key == "time_budget":
            return any(token in text for token in ["hour", "час", "week", "недел", "day", "день"])
        if question_key == "resources":
            return any(token in text for token in ["есть", "have", "доступ", "опыт", "ноут", "интернет", "деньг"])
        if question_key == "constraints":
            return any(token in text for token in ["могу", "не могу", "работ", "время", "деньг", "health", "здоров"])
        return True

    def _nullable_str(self, value) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None