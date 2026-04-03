from __future__ import annotations

from app.services.ai_profiling_service import AIProfilingService


class ProfilingSummaryService:
    def __init__(self):
        self.ai_service = AIProfilingService()

    async def build_summary(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
    ) -> dict:
        try:
            result = await self.ai_service.build_profiling_summary(
                goal_title=goal_title,
                goal_description=goal_description,
                answers=answers,
            )
            return self._normalize_summary(result)
        except Exception:
            return self._build_fallback_summary(answers)

    def _normalize_summary(self, result: dict) -> dict:
        return {
            "goal_outcome": self._nullable_str(result.get("goal_outcome")),
            "current_state": self._nullable_str(result.get("current_state")),
            "deadline": self._nullable_str(result.get("deadline")),
            "resources": self._normalize_list(result.get("resources")),
            "constraints": self._normalize_list(result.get("constraints")),
            "time_budget": self._nullable_str(result.get("time_budget")),
            "past_attempts": self._nullable_str(result.get("past_attempts")),
            "main_obstacles": self._normalize_list(result.get("main_obstacles")),
            "motivation": self._nullable_str(result.get("motivation")),
            "daily_routine": self._nullable_str(result.get("daily_routine")),
            "coach_style": self._nullable_str(result.get("coach_style")),
            "planning_notes": self._normalize_list(result.get("planning_notes")),
            "plan_confidence": self._nullable_str(result.get("plan_confidence")),
        }

    def _build_fallback_summary(self, answers: dict[str, str]) -> dict:
        return {
            "goal_outcome": answers.get("goal_outcome"),
            "current_state": answers.get("current_level") or answers.get("current_state"),
            "deadline": answers.get("deadline"),
            "resources": self._split_text(answers.get("resources")),
            "constraints": self._split_text(answers.get("constraints")),
            "time_budget": answers.get("time_budget"),
            "past_attempts": answers.get("past_attempts"),
            "main_obstacles": self._split_text(answers.get("obstacles")),
            "motivation": answers.get("motivation"),
            "daily_routine": answers.get("daily_routine"),
            "coach_style": answers.get("coach_style"),
            "planning_notes": [],
            "plan_confidence": "medium",
        }

    def _nullable_str(self, value) -> str | None:
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def _normalize_list(self, value) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(x).strip() for x in value if str(x).strip()]
        if isinstance(value, str):
            return self._split_text(value)
        return [str(value).strip()] if str(value).strip() else []

    def _split_text(self, value: str | None) -> list[str]:
        if not value:
            return []
        raw = str(value)
        parts = []
        for chunk in raw.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)
        return parts