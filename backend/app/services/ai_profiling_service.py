from __future__ import annotations

from typing import Any

from app.config import settings
from app.services.openai_client import OpenAIClient
from app.services.profiling_prompt_builder import ProfilingPromptBuilder


class AIProfilingService:
    def __init__(self):
        self.prompt_builder = ProfilingPromptBuilder()
        self.llm = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def generate_questions(self, goal: str) -> dict[str, Any]:
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(goal)

        raw_result = await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return self._normalize_generate_questions_result(raw_result)

    async def judge_answer(
        self,
        goal_title: str,
        goal_description: str | None,
        question: dict,
        user_answer: str,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        system_prompt = self.prompt_builder.build_answer_judge_system_prompt()
        user_prompt = self.prompt_builder.build_answer_judge_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            question_key=question.get("key", ""),
            question_text=question.get("text", ""),
            example_answer=question.get("example_answer"),
            user_answer=user_answer,
            answers=answers,
            suggested_options=question.get("suggested_options"),
        )

        raw_result = await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return self._normalize_judge_answer_result(raw_result)

    async def select_next_question(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
        candidate_questions: list[dict],
    ) -> dict[str, Any]:
        system_prompt = self.prompt_builder.build_next_question_selector_system_prompt()
        user_prompt = self.prompt_builder.build_next_question_selector_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            answers=answers,
            candidate_questions=candidate_questions,
        )

        raw_result = await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return self._normalize_select_next_question_result(raw_result)

    async def build_profiling_summary(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
    ) -> dict[str, Any]:
        system_prompt = self.prompt_builder.build_profiling_summary_system_prompt()
        user_prompt = self.prompt_builder.build_profiling_summary_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            answers=answers,
        )

        raw_result = await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )
        return self._normalize_profiling_summary_result(raw_result)

    def _normalize_generate_questions_result(self, result: Any) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}

        raw_questions = payload.get("questions")
        questions: list[dict[str, Any]] = []

        if isinstance(raw_questions, list):
            for index, item in enumerate(raw_questions, start=1):
                if not isinstance(item, dict):
                    continue

                question_key = self._safe_text(item.get("key")) or f"question_{index}"
                question_text = self._safe_text(item.get("text"))
                if not question_text:
                    continue

                example_answer = self._safe_text(item.get("example_answer"))
                question_type = self._normalize_question_type(item.get("question_type"))
                suggested_options = self._normalize_options(item.get("suggested_options"))
                allow_free_text = self._normalize_bool(item.get("allow_free_text"), default=True)

                questions.append(
                    {
                        "id": self._safe_text(item.get("id")) or f"q{index}",
                        "key": question_key,
                        "text": question_text,
                        "example_answer": example_answer,
                        "question_type": question_type,
                        "suggested_options": suggested_options,
                        "allow_free_text": allow_free_text,
                    }
                )

        coach_message = self._safe_text(payload.get("coach_message"))

        return {
            "questions": questions,
            "coach_message": coach_message,
        }

    def _normalize_judge_answer_result(self, result: Any) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}

        accepted = self._normalize_bool(payload.get("accepted"), default=False)
        reason = self._safe_text(payload.get("reason")) or (
            "accepted" if accepted else "insufficient_detail"
        )

        return {
            "accepted": accepted,
            "reason": reason,
            "missing_info": self._safe_text(payload.get("missing_info")),
            "feedback_message": self._safe_text(payload.get("feedback_message")),
            "follow_up_question": self._safe_text(payload.get("follow_up_question")),
            "example_answer": self._safe_text(payload.get("example_answer")),
            "suggested_options": self._normalize_options(payload.get("suggested_options")),
        }

    def _normalize_select_next_question_result(self, result: Any) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}

        is_completed = self._normalize_bool(payload.get("is_completed"), default=False)
        next_question_key = self._safe_text(payload.get("next_question_key"))
        reason = self._safe_text(payload.get("reason")) or (
            "profiling_complete" if is_completed else "next_question_selected"
        )

        if is_completed:
            next_question_key = None

        return {
            "is_completed": is_completed,
            "next_question_key": next_question_key,
            "reason": reason,
        }

    def _normalize_profiling_summary_result(self, result: Any) -> dict[str, Any]:
        payload = result if isinstance(result, dict) else {}

        return {
            "goal_outcome": self._safe_text(payload.get("goal_outcome")),
            "current_state": self._safe_text(payload.get("current_state")),
            "deadline": self._safe_text(payload.get("deadline")),
            "resources": self._normalize_string_list(payload.get("resources")),
            "constraints": self._normalize_string_list(payload.get("constraints")),
            "time_budget": self._safe_text(payload.get("time_budget")),
            "past_attempts": self._safe_text(payload.get("past_attempts")),
            "main_obstacles": self._normalize_string_list(payload.get("main_obstacles")),
            "motivation": self._safe_text(payload.get("motivation")),
            "daily_routine": self._safe_text(payload.get("daily_routine")),
            "coach_style": self._safe_text(payload.get("coach_style")),
            "planning_notes": self._normalize_string_list(payload.get("planning_notes")),
            "plan_confidence": self._normalize_plan_confidence(payload.get("plan_confidence")),
            "success_metrics": self._normalize_string_list(payload.get("success_metrics")),
            "environment": self._normalize_string_list(payload.get("environment")),
            "risk_factors": self._normalize_string_list(payload.get("risk_factors")),
            "preferred_execution_style": self._safe_text(
                payload.get("preferred_execution_style")
            ),
        }

    def _normalize_question_type(self, value: Any) -> str:
        normalized = (self._safe_text(value) or "text").lower()
        allowed = {"text", "choice", "choice_or_text"}
        return normalized if normalized in allowed else "text"

    def _normalize_options(self, value: Any) -> list[str] | None:
        if not isinstance(value, list):
            return None

        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None

    def _normalize_string_list(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                text_value = self._safe_text(item)
                if text_value:
                    result.append(text_value)
            return result

        if isinstance(value, str):
            text_value = value.strip()
            return [text_value] if text_value else []

        text_value = self._safe_text(value)
        return [text_value] if text_value else []

    def _normalize_plan_confidence(self, value: Any) -> str | None:
        normalized = (self._safe_text(value) or "").lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return None

    def _normalize_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        normalized = str(value).strip().lower()
        if normalized in {"true", "1", "yes", "y"}:
            return True
        if normalized in {"false", "0", "no", "n"}:
            return False

        return default

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        normalized = str(value).strip()
        return normalized or None