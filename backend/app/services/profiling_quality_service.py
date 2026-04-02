from __future__ import annotations

from app.services.ai_profiling_service import AIProfilingService


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

        # 1. Быстрый локальный guardrail
        if not cleaned_answer:
            return self._fallback_result(
                accepted=False,
                reason="empty_answer",
                missing_info="Answer is empty",
                feedback_message="Ответ пустой.",
                follow_up_question="Ответь на вопрос чуть подробнее.",
                example_answer=question.get("example_answer"),
                source="rule_based",
            )

        if len(cleaned_answer) < 8:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Answer is too short",
                feedback_message="Ответ слишком короткий.",
                follow_up_question="Можешь ответить чуть подробнее и конкретнее?",
                example_answer=question.get("example_answer"),
                source="rule_based",
            )

        # 2. Основная AI-оценка
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
            # 3. Fallback, если AI сломался
            return self._rule_based_evaluation(question=question, answer=cleaned_answer)

    def _normalize_ai_result(self, result: dict, question: dict) -> dict:
        accepted = bool(result.get("accepted", False))

        return {
            "accepted": accepted,
            "reason": str(result.get("reason") or ("accepted" if accepted else "insufficient_detail")),
            "missing_info": self._nullable_str(result.get("missing_info")),
            "feedback_message": self._nullable_str(result.get("feedback_message")),
            "follow_up_question": self._nullable_str(result.get("follow_up_question")),
            "example_answer": self._nullable_str(result.get("example_answer")) or question.get("example_answer"),
            "source": "ai",
        }

    def _rule_based_evaluation(self, question: dict, answer: str) -> dict:
        text = answer.strip()
        words = text.split()

        if len(words) < 3:
            return self._fallback_result(
                accepted=False,
                reason="too_short",
                missing_info="Not enough detail",
                feedback_message="Слишком мало информации.",
                follow_up_question="Ответь чуть подробнее, добавь конкретику.",
                example_answer=question.get("example_answer"),
                source="rule_based",
            )

        if question.get("key") in {"time_budget", "constraints", "resources"} and len(text) < 15:
            return self._fallback_result(
                accepted=False,
                reason="not_specific_enough",
                missing_info="Need more practical detail",
                feedback_message="Ответ пока слишком общий.",
                follow_up_question="Добавь больше практической конкретики: время, условия, ограничения или ресурсы.",
                example_answer=question.get("example_answer"),
                source="rule_based",
            )

        return self._fallback_result(
            accepted=True,
            reason="accepted_by_fallback",
            missing_info=None,
            feedback_message=None,
            follow_up_question=None,
            example_answer=None,
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
        source: str,
    ) -> dict:
        return {
            "accepted": accepted,
            "reason": reason,
            "missing_info": missing_info,
            "feedback_message": feedback_message,
            "follow_up_question": follow_up_question,
            "example_answer": example_answer,
            "source": source,
        }

    def _nullable_str(self, value) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None