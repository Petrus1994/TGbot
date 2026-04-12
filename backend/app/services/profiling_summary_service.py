from __future__ import annotations

from typing import Any

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
            if not isinstance(result, dict):
                return self._build_fallback_summary(answers)
            return self._normalize_summary(result, answers)
        except Exception:
            return self._build_fallback_summary(answers)

    def _normalize_summary(
        self,
        result: dict[str, Any],
        answers: dict[str, str],
    ) -> dict[str, Any]:
        goal_outcome = self._first_non_empty(
            result.get("goal_outcome"),
            result.get("success_metrics"),
            answers.get("goal_outcome"),
        )

        current_state = self._first_non_empty(
            result.get("current_state"),
            result.get("current_level"),
            answers.get("current_level"),
            answers.get("current_state"),
        )

        deadline = self._first_non_empty(
            result.get("deadline"),
            answers.get("deadline"),
        )

        resources = self._merge_lists(
            result.get("resources"),
            answers.get("resources"),
        )

        constraints = self._merge_lists(
            result.get("constraints"),
            answers.get("constraints"),
        )

        time_budget = self._first_non_empty(
            result.get("time_budget"),
            answers.get("time_budget"),
        )

        past_attempts = self._first_non_empty(
            result.get("past_attempts"),
            answers.get("past_attempts"),
        )

        main_obstacles = self._merge_lists(
            result.get("main_obstacles"),
            result.get("risk_factors"),
            answers.get("main_obstacles"),
            answers.get("obstacles"),
        )

        motivation = self._first_non_empty(
            result.get("motivation"),
            answers.get("motivation"),
        )

        daily_routine = self._first_non_empty(
            result.get("daily_routine"),
            answers.get("daily_routine"),
        )

        coach_style = self._first_non_empty(
            result.get("coach_style"),
            result.get("preferred_execution_style"),
            answers.get("coach_style"),
            answers.get("preferred_execution_style"),
        )

        planning_notes = self._merge_lists(
            result.get("planning_notes"),
            result.get("environment"),
            answers.get("environment"),
        )

        plan_confidence = self._normalize_plan_confidence(
            result.get("plan_confidence")
        )

        success_metrics = self._merge_lists(
            result.get("success_metrics"),
            answers.get("success_metrics"),
        )

        environment = self._merge_lists(
            result.get("environment"),
            answers.get("environment"),
        )

        risk_factors = self._merge_lists(
            result.get("risk_factors"),
            answers.get("risk_factors"),
        )

        preferred_execution_style = self._first_non_empty(
            result.get("preferred_execution_style"),
            answers.get("preferred_execution_style"),
        )

        return {
            "goal_outcome": goal_outcome,
            "current_state": current_state,
            "deadline": deadline,
            "resources": resources,
            "constraints": constraints,
            "time_budget": time_budget,
            "past_attempts": past_attempts,
            "main_obstacles": main_obstacles,
            "motivation": motivation,
            "daily_routine": daily_routine,
            "coach_style": coach_style,
            "planning_notes": planning_notes,
            "plan_confidence": plan_confidence,
            "success_metrics": success_metrics,
            "environment": environment,
            "risk_factors": risk_factors,
            "preferred_execution_style": preferred_execution_style,
        }

    def _build_fallback_summary(self, answers: dict[str, str]) -> dict[str, Any]:
        constraints = self._merge_lists(
            answers.get("constraints"),
        )
        resources = self._merge_lists(
            answers.get("resources"),
        )
        obstacles = self._merge_lists(
            answers.get("main_obstacles"),
            answers.get("obstacles"),
        )
        environment = self._merge_lists(
            answers.get("environment"),
        )
        success_metrics = self._merge_lists(
            answers.get("success_metrics"),
        )
        planning_notes = self._merge_lists(
            answers.get("planning_notes"),
            environment,
        )

        risk_factors = list(obstacles)
        if constraints:
            for item in constraints:
                if item not in risk_factors:
                    risk_factors.append(item)

        preferred_execution_style = self._first_non_empty(
            answers.get("preferred_execution_style"),
        )

        return {
            "goal_outcome": self._first_non_empty(
                answers.get("goal_outcome"),
            ),
            "current_state": self._first_non_empty(
                answers.get("current_level"),
                answers.get("current_state"),
            ),
            "deadline": self._first_non_empty(
                answers.get("deadline"),
            ),
            "resources": resources,
            "constraints": constraints,
            "time_budget": self._first_non_empty(
                answers.get("time_budget"),
            ),
            "past_attempts": self._first_non_empty(
                answers.get("past_attempts"),
            ),
            "main_obstacles": obstacles,
            "motivation": self._first_non_empty(
                answers.get("motivation"),
            ),
            "daily_routine": self._first_non_empty(
                answers.get("daily_routine"),
            ),
            "coach_style": self._first_non_empty(
                answers.get("coach_style"),
            ),
            "planning_notes": planning_notes,
            "plan_confidence": self._infer_fallback_plan_confidence(
                answers=answers,
                constraints=constraints,
                resources=resources,
                obstacles=obstacles,
            ),
            "success_metrics": success_metrics,
            "environment": environment,
            "risk_factors": risk_factors,
            "preferred_execution_style": preferred_execution_style,
        }

    def _first_non_empty(self, *values: Any) -> str | None:
        for value in values:
            normalized = self._nullable_str(value)
            if normalized:
                return normalized
        return None

    def _nullable_str(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, list):
            items = [str(x).strip() for x in value if str(x).strip()]
            return ", ".join(items) if items else None

        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                key_str = str(key).strip()
                item_str = str(item).strip()
                if key_str and item_str:
                    parts.append(f"{key_str}: {item_str}")
            return "; ".join(parts) if parts else None

        value_str = str(value).strip()
        return value_str or None

    def _normalize_list(self, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, list):
            result: list[str] = []
            for item in value:
                text_value = self._nullable_str(item)
                if text_value:
                    result.extend(self._split_text(text_value))
            return self._deduplicate_preserve_order(result)

        if isinstance(value, dict):
            result: list[str] = []
            for key, item in value.items():
                key_str = str(key).strip()
                item_str = self._nullable_str(item)
                if key_str and item_str:
                    result.append(f"{key_str}: {item_str}")
            return self._deduplicate_preserve_order(result)

        if isinstance(value, str):
            return self._split_text(value)

        text_value = str(value).strip()
        return [text_value] if text_value else []

    def _merge_lists(self, *values: Any) -> list[str]:
        merged: list[str] = []
        for value in values:
            merged.extend(self._normalize_list(value))
        return self._deduplicate_preserve_order(merged)

    def _split_text(self, value: str | None) -> list[str]:
        if not value:
            return []

        raw = str(value).strip()
        if not raw:
            return []

        normalized = (
            raw.replace("\n", ",")
            .replace(";", ",")
            .replace("•", ",")
            .replace("—", ",")
        )

        parts: list[str] = []
        for chunk in normalized.split(","):
            chunk = chunk.strip()
            if chunk:
                parts.append(chunk)

        return self._deduplicate_preserve_order(parts)

    def _deduplicate_preserve_order(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for item in items:
            normalized = item.strip()
            if not normalized:
                continue

            lowered = normalized.lower()
            if lowered in seen:
                continue

            seen.add(lowered)
            result.append(normalized)

        return result

    def _normalize_plan_confidence(self, value: Any) -> str | None:
        normalized = (self._nullable_str(value) or "").strip().lower()
        if normalized in {"low", "medium", "high"}:
            return normalized
        return None

    def _infer_fallback_plan_confidence(
        self,
        *,
        answers: dict[str, str],
        constraints: list[str],
        resources: list[str],
        obstacles: list[str],
    ) -> str:
        score = 0

        for key in (
            "goal_outcome",
            "current_level",
            "constraints",
            "resources",
            "motivation",
            "coach_style",
            "time_budget",
            "past_attempts",
            "daily_routine",
        ):
            value = answers.get(key)
            if value and str(value).strip():
                score += 1

        if resources:
            score += 1
        if constraints:
            score += 1
        if obstacles:
            score += 1

        if score >= 10:
            return "high"
        if score >= 6:
            return "medium"
        return "low"