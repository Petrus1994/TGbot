from __future__ import annotations

import re
from typing import Any

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
    "любой",
    "не принципиально",
    "как пойдет",
    "idk",
    "not sure",
    "maybe",
    "whatever",
    "any",
}

GENERIC_LOW_SIGNAL_PATTERNS = {
    "хочу стать лучше",
    "хочу стать успешнее",
    "хочу развиваться",
    "хочу изменить жизнь",
    "хочу больше денег",
    "хочу дисциплину",
    "хочу результат",
    "just improve",
    "be better",
    "make more money",
    "be successful",
}

SHORT_BUT_VALID_KEYS = {
    "coach_style",
}

NUMERIC_SIGNAL_KEYS = {
    "deadline",
    "time_budget",
    "body_metrics",
    "current_income",
}

PRACTICAL_DETAIL_KEYS = {
    "constraints",
    "resources",
    "motivation",
    "daily_routine",
    "main_obstacles",
    "past_attempts",
    "environment",
    "practice_format",
    "training_access",
    "training_environment",
    "nutrition_state",
    "nutrition_reality",
    "monetization_path",
    "income_model",
    "current_income_state",
    "target_use_case",
    "habit_failure_pattern",
}

CHOICE_NORMALIZATION = {
    "aggressive": "aggressive",
    "balanced": "balanced",
    "soft": "soft",
    "жесткий": "aggressive",
    "жёсткий": "aggressive",
    "агрессивный": "aggressive",
    "баланс": "balanced",
    "сбалансированный": "balanced",
    "мягкий": "soft",
    "мягко": "soft",
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
        cleaned_answer = self._clean_text(answer)
        question_key = str(question.get("key") or "").strip()
        question_type = str(question.get("question_type") or "text").strip().lower()

        if not cleaned_answer:
            return self._fallback_result(
                accepted=False,
                reason="empty_answer",
                missing_info="Answer is empty",
                feedback_message="Ответ пустой.",
                follow_up_question="Ответь на вопрос чуть подробнее.",
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
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
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        if self._looks_generic_low_signal(cleaned_answer, question_key):
            return self._fallback_result(
                accepted=False,
                reason="generic_low_signal_answer",
                missing_info="The answer is too generic",
                feedback_message=self._build_generic_feedback(question_key),
                follow_up_question=self._build_specific_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        if question_key == "coach_style" or question_type == "choice":
            return self._evaluate_choice_answer(question, cleaned_answer)

        if len(cleaned_answer) < 8 and question_key not in SHORT_BUT_VALID_KEYS:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Answer is too short",
                feedback_message=self._build_short_feedback(question_key),
                follow_up_question=self._build_short_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        rule_based_result = self._rule_based_precheck(question=question, answer=cleaned_answer)
        if rule_based_result is not None:
            return rule_based_result

        try:
            result = await self.ai_service.judge_answer(
                goal_title=goal_title,
                goal_description=goal_description,
                question=question,
                user_answer=cleaned_answer,
                answers=answers,
            )
            return self._normalize_ai_result(result, question, cleaned_answer)
        except Exception:
            return self._rule_based_evaluation(question=question, answer=cleaned_answer)

    def _evaluate_choice_answer(self, question: dict, cleaned_answer: str) -> dict:
        question_key = str(question.get("key") or "").strip()
        allowed_options = self._get_suggested_options(question) or []

        normalized_choice = self._normalize_choice_value(cleaned_answer)
        normalized_allowed = {
            self._normalize_choice_value(option): option
            for option in allowed_options
            if self._normalize_choice_value(option)
        }

        if normalized_choice and normalized_choice in normalized_allowed:
            canonical_value = normalized_allowed[normalized_choice]

            return self._fallback_result(
                accepted=True,
                reason="choice_selected",
                missing_info=None,
                feedback_message=None,
                follow_up_question=None,
                example_answer=None,
                suggested_options=allowed_options,
                source="rule_based",
            )

        return self._fallback_result(
            accepted=False,
            reason="invalid_choice",
            missing_info="Expected one of the allowed options",
            feedback_message="Здесь лучше выбрать один из предложенных вариантов.",
            follow_up_question=self._build_choice_follow_up(question_key, allowed_options),
            example_answer=None,
            suggested_options=allowed_options,
            source="rule_based",
        )

    def _rule_based_precheck(self, question: dict, answer: str) -> dict | None:
        question_key = str(question.get("key") or "").strip()
        question_type = str(question.get("question_type") or "text").strip().lower()

        if question_type == "choice_or_text":
            options = self._get_suggested_options(question) or []
            normalized_answer = self._normalize_choice_value(answer)
            normalized_options = {
                self._normalize_choice_value(option): option
                for option in options
                if self._normalize_choice_value(option)
            }

            if normalized_answer and normalized_answer in normalized_options:
                return self._fallback_result(
                    accepted=True,
                    reason="choice_or_text_option_selected",
                    missing_info=None,
                    feedback_message=None,
                    follow_up_question=None,
                    example_answer=None,
                    suggested_options=options,
                    source="rule_based",
                )

        if question_key in NUMERIC_SIGNAL_KEYS and not self._contains_numeric_signal(answer):
            return self._fallback_result(
                accepted=False,
                reason="missing_numeric_signal",
                missing_info="Need at least an approximate number or range",
                feedback_message=self._build_numeric_feedback(question_key),
                follow_up_question=self._build_numeric_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        if question_key in PRACTICAL_DETAIL_KEYS and len(answer) < 15:
            return self._fallback_result(
                accepted=False,
                reason="not_specific_enough",
                missing_info="Need more practical detail",
                feedback_message=self._build_generic_feedback(question_key),
                follow_up_question=self._build_specific_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        return None

    def _normalize_ai_result(
        self,
        result: dict,
        question: dict,
        cleaned_answer: str,
    ) -> dict:
        accepted = bool(result.get("accepted", False))
        question_key = str(question.get("key") or "").strip()

        raw_example = self._nullable_str(result.get("example_answer"))
        fallback_example = self._safe_example(question.get("example_answer"))
        example_answer = self._choose_example(raw_example, fallback_example, question_key)

        suggested_options = self._normalize_options(
            result.get("suggested_options"),
            fallback=self._get_suggested_options(question),
        )

        feedback_message = self._nullable_str(result.get("feedback_message"))
        if not feedback_message and not accepted:
            feedback_message = self._build_generic_feedback(question_key)

        follow_up_question = self._nullable_str(result.get("follow_up_question"))
        if not follow_up_question and not accepted:
            follow_up_question = self._build_short_follow_up(question_key)

        if accepted:
            if question_key in NUMERIC_SIGNAL_KEYS and not self._contains_numeric_signal(cleaned_answer):
                accepted = False
                feedback_message = self._build_numeric_feedback(question_key)
                follow_up_question = self._build_numeric_follow_up(question_key)

            if question_key in PRACTICAL_DETAIL_KEYS and len(cleaned_answer) < 15:
                accepted = False
                feedback_message = self._build_generic_feedback(question_key)
                follow_up_question = self._build_specific_follow_up(question_key)

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

        if len(words) < 3 and question_key not in SHORT_BUT_VALID_KEYS:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Not enough detail",
                feedback_message=self._build_short_feedback(question_key),
                follow_up_question=self._build_short_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        if question_key in NUMERIC_SIGNAL_KEYS and not self._contains_numeric_signal(text):
            return self._fallback_result(
                accepted=False,
                reason="missing_numeric_signal",
                missing_info="Need more practical numeric detail",
                feedback_message=self._build_numeric_feedback(question_key),
                follow_up_question=self._build_numeric_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        if question_key in PRACTICAL_DETAIL_KEYS and len(text) < 15:
            return self._fallback_result(
                accepted=False,
                reason="not_specific_enough",
                missing_info="Need more practical detail",
                feedback_message=self._build_generic_feedback(question_key),
                follow_up_question=self._build_specific_follow_up(question_key),
                example_answer=self._safe_example(question.get("example_answer")),
                suggested_options=self._get_suggested_options(question),
                source="rule_based",
            )

        return self._fallback_result(
            accepted=True,
            reason="accepted_by_fallback",
            missing_info=None,
            feedback_message=None,
            follow_up_question=None,
            example_answer=None,
            suggested_options=self._get_suggested_options(question),
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

    def _clean_text(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", str(value).strip())

    def _looks_uncertain(self, answer: str) -> bool:
        normalized = answer.strip().lower()
        return normalized in UNCERTAIN_ANSWER_PATTERNS

    def _looks_generic_low_signal(self, answer: str, question_key: str) -> bool:
        if question_key in {"motivation", "goal_outcome", "main_obstacles"}:
            normalized = answer.strip().lower()
            return normalized in GENERIC_LOW_SIGNAL_PATTERNS
        return False

    def _contains_numeric_signal(self, answer: str) -> bool:
        text = answer.lower()

        if re.search(r"\d", text):
            return True

        numeric_words = [
            "one", "two", "three", "four", "five",
            "один", "два", "три", "четыр", "пять",
            "few", "several", "несколько",
            "week", "weeks", "month", "months", "year", "years",
            "недел", "меся", "год", "час", "hours", "hour",
            "%", "percent", "процент",
        ]

        return any(token in text for token in numeric_words)

    def _build_uncertain_feedback(self, question_key: str) -> str:
        if question_key == "deadline":
            return "Нормально ответить примерно. Не нужен идеальный срок."
        if question_key == "time_budget":
            return "Даже примерная оценка времени уже полезна для реалистичного плана."
        if question_key == "motivation":
            return "Важно понять, зачем тебе эта цель, даже если ответ пока неидеальный."
        return "Можно ответить примерно — этого уже хватит, чтобы построить хороший план."

    def _build_uncertain_follow_up(self, question_key: str) -> str:
        if question_key == "deadline":
            return "Дай хотя бы ориентир: это скорее 1–3 месяца, 3–6 месяцев, 6–12 месяцев или дольше?"
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
            "goal_outcome": "Пока неясно, какой именно результат ты хочешь получить.",
            "main_obstacles": "Пока непонятно, что именно мешает тебе чаще всего.",
        }
        return feedback_map.get(question_key, "Ответ пока слишком короткий.")

    def _build_short_follow_up(self, question_key: str) -> str:
        follow_up_map = {
            "goal_outcome": "Опиши конкретнее: какой именно результат ты хочешь и как он будет выглядеть?",
            "current_level": "Опиши текущую ситуацию чуть конкретнее: что у тебя уже есть, а чего ещё нет?",
            "constraints": "Какие есть ограничения по времени, деньгам, здоровью, работе или условиям?",
            "resources": "Что у тебя уже есть для этой цели: деньги, навыки, инструменты, связи, доступ?",
            "motivation": "Почему эта цель важна именно для тебя? Что изменится, если ты её достигнешь?",
            "deadline": "За какой срок ты хочешь этого добиться хотя бы примерно?",
            "time_budget": "Сколько часов в неделю ты реально готов уделять этой цели?",
            "main_obstacles": "Что чаще всего тебя срывает: время, хаос, страх, усталость, отсутствие системы или что-то ещё?",
        }
        return follow_up_map.get(question_key, "Ответь чуть подробнее и конкретнее.")

    def _build_generic_feedback(self, question_key: str) -> str:
        feedback_map = {
            "goal_outcome": "Результат пока описан слишком общо. Нужна более чёткая конечная точка.",
            "current_level": "Ты описал ситуацию слишком общо. Нужна более ясная стартовая точка.",
            "constraints": "Ты назвал ограничения слишком общо. Нужны практические детали.",
            "resources": "Ты перечислил ресурсы слишком расплывчато. Нужны более конкретные опоры.",
            "motivation": "Ты указал мотивацию слишком общо. Нужно понять, что для тебя реально стоит на кону.",
            "deadline": "Срок пока неясный. Для плана нужен хотя бы примерный ориентир.",
            "time_budget": "По времени пока мало конкретики. Это важно для реалистичного плана.",
            "coach_style": "Нужно понять, какой формат коучинга тебе подходит.",
            "main_obstacles": "Нужно точнее понять, какие именно препятствия ломают тебе систему.",
            "daily_routine": "Нужна чуть более реальная картина твоего режима.",
            "environment": "Нужно лучше понять, в каких условиях ты реально будешь это делать.",
            "past_attempts": "Нужно точнее понять, что ты уже пробовал и где именно всё ломалось.",
        }
        return feedback_map.get(question_key, "Ответ пока слишком общий.")

    def _build_specific_follow_up(self, question_key: str) -> str:
        follow_up_map = {
            "goal_outcome": "Добавь конкретику: какой результат, в каких цифрах или признаках, и в каком формате ты считаешь его успехом?",
            "constraints": "Добавь конкретику: время, деньги, здоровье, работа, семья, энергия или другие условия.",
            "resources": "Перечисли реальные ресурсы: деньги, навыки, инструменты, связи, доступ к платформам, залу, курсам или клиентам.",
            "motivation": "Скажи конкретнее: зачем тебе эта цель и что изменится после результата?",
            "deadline": "Укажи хотя бы примерный срок: недели, месяцы или дольше.",
            "time_budget": "Добавь практическую оценку: сколько часов в день или неделю ты реально готов выделять?",
            "main_obstacles": "Назови 1–3 главных препятствия, которые реально ломают прогресс.",
            "daily_routine": "Опиши, когда у тебя реально есть свободные окна по времени.",
            "past_attempts": "Коротко опиши, что ты уже пробовал и почему это не удержалось.",
            "environment": "Опиши реальные условия: где ты работаешь/учишься/тренируешься и что там помогает или мешает.",
        }
        return follow_up_map.get(question_key, "Добавь чуть больше конкретики.")

    def _build_numeric_feedback(self, question_key: str) -> str:
        feedback_map = {
            "deadline": "Для срока нужен хотя бы примерный числовой ориентир.",
            "time_budget": "Для времени нужна хотя бы примерная цифра или диапазон.",
            "body_metrics": "Для физической цели нужны хотя бы примерные параметры.",
            "current_income": "Для денежной цели нужна хотя бы примерная отправная точка.",
        }
        return feedback_map.get(question_key, "Нужен хотя бы примерный числовой ориентир.")

    def _build_numeric_follow_up(self, question_key: str) -> str:
        follow_up_map = {
            "deadline": "Укажи хотя бы примерно: сколько недель или месяцев ты даёшь себе на эту цель?",
            "time_budget": "Сколько часов в неделю ты реально готов выделять: меньше 5, 5–10, 10+ или свой вариант?",
            "body_metrics": "Напиши хотя бы примерно: рост, вес и если знаешь — процент жира или желаемый вес.",
            "current_income": "Напиши хотя бы примерно: сколько ты сейчас зарабатываешь или какая у тебя текущая ситуация по доходу?",
        }
        return follow_up_map.get(question_key, "Добавь хотя бы примерную цифру или диапазон.")

    def _build_choice_follow_up(self, question_key: str, options: list[str] | None) -> str:
        if options:
            joined = ", ".join(options)
            return f"Выбери один из вариантов: {joined}."
        if question_key == "coach_style":
            return "Выбери один вариант: aggressive, balanced или soft."
        return "Выбери один из предложенных вариантов."

    def _get_suggested_options(self, question: dict) -> list[str] | None:
        raw = question.get("suggested_options")
        if isinstance(raw, list):
            items = [str(item).strip() for item in raw if str(item).strip()]
            return items or None

        question_key = str(question.get("key") or "").strip()
        options_map = {
            "coach_style": ["aggressive", "balanced", "soft"],
            "deadline": ["1-3 months", "3-6 months", "6-12 months", "no strict deadline"],
            "time_budget": ["<5 hours/week", "5-10 hours/week", "10+ hours/week"],
        }
        return options_map.get(question_key)

    def _normalize_options(self, value: Any, fallback: list[str] | None = None) -> list[str] | None:
        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return items or fallback
        return fallback

    def _safe_example(self, value: Any) -> str | None:
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
            return any(
                option in text
                for option in ["aggressive", "balanced", "soft", "жест", "мяг", "баланс"]
            )
        if question_key == "deadline":
            return any(token in text for token in ["month", "week", "год", "меся", "недел", "срок"])
        if question_key == "time_budget":
            return any(token in text for token in ["hour", "час", "week", "недел", "day", "день"])
        if question_key in {"resources", "constraints"}:
            return any(
                token in text
                for token in ["есть", "have", "доступ", "опыт", "ноут", "интернет", "деньг", "работ", "время"]
            )
        return True

    def _normalize_choice_value(self, value: str | None) -> str | None:
        if not value:
            return None
        normalized = str(value).strip().lower()
        return CHOICE_NORMALIZATION.get(normalized, normalized)

    def _nullable_str(self, value: Any) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None