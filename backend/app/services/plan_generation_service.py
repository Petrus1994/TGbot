from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any

from sqlalchemy import text

from app.config import settings
from app.core.exceptions import (
    AIPlanGenerationError,
    AIResponseValidationError,
    GoalNotFoundError,
    ProfilingIncompleteError,
)
from app.db import engine
from app.schemas.ai_plan_v2 import AIPlanResponseV2
from app.schemas.goal_generation import GoalGenerationContext
from app.services.openai_client import OpenAIClient
from app.services.plan_prompt_builder import PlanPromptBuilder
from app.services.plan_service import save_generated_plan


class PlanGenerationService:
    ALLOWED_CADENCE_TYPES = {"daily", "weekly", "specific_weekdays"}
    ALLOWED_PROOF_TYPES = {"text", "photo", "screenshot", "file"}

    FORBIDDEN_PHRASES = [
        "постарайся",
        "думай",
        "верь в себя",
        "не сдавайся",
        "будь мотивирован",
        "stay consistent",
        "try your best",
        "stay motivated",
        "believe in yourself",
        "don't give up",
    ]

    def __init__(self) -> None:
        self.prompt_builder = PlanPromptBuilder()
        self.llm_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    # =========================================================
    # 🔥 MAIN ENTRY
    # =========================================================

    async def generate_plan(self, goal_id: str, regenerate: bool = False):
        if not settings.ai_plan_generation_enabled:
            raise AIPlanGenerationError("ai_plan_generation_disabled")

        context = await self._load_context(goal_id)
        self._validate_context(context)

        # 🔥 НОВОЕ: execution profile (мозг коуча)
        execution_profile = self._build_execution_profile(context)

        response_language = self._infer_response_language(context)

        system_prompt = self.prompt_builder.build_system_prompt(context)
        user_prompt = self.prompt_builder.build_user_prompt(context)

        # 🔥 ДОБАВЛЯЕМ "мышление" в prompt
        user_prompt = f"""{user_prompt}

========================================
EXECUTION PROFILE (CRITICAL)
========================================
{execution_profile}

Use this to ADAPT the plan:
- simplify if needed
- reduce overload
- increase adherence
- avoid known failure patterns

========================================
LANGUAGE RULE
========================================
Return all content in {response_language}

========================================
PROOF RULES
========================================
Proof must be:
- easy
- fast
- believable

"""

        ai_response = await self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_language=response_language,
        )

        plan_payload = self._map_to_plan_payload(
            goal_id=goal_id,
            ai_response=ai_response,
        )

        try:
            return save_generated_plan(
                goal_id=goal_id,
                title=plan_payload["title"],
                summary=plan_payload["summary"],
                content=plan_payload["content"],
                status=plan_payload["status"],
            )
        except Exception as e:
            print(f"❌ SAVE GENERATED PLAN ERROR: {e!r}")
            raise AIPlanGenerationError(f"save_generated_plan_failed: {e}") from e

    # =========================================================
    # 🔥 НОВОЕ: CORE INTELLIGENCE LAYER
    # =========================================================

    def _build_execution_profile(self, context: GoalGenerationContext) -> str:
        """
        Это главный апгрейд.
        Здесь мы превращаем profiling → реальное мышление коуча
        """

        signals = []

        # время
        if context.time_budget:
            if any(x in context.time_budget.lower() for x in ["1", "2", "hour", "час"]):
                signals.append("low_time")
            else:
                signals.append("normal_time")

        # дисциплина (по прошлым попыткам)
        if context.past_attempts:
            if any(x in context.past_attempts.lower() for x in ["fail", "не получилось", "бросал"]):
                signals.append("low_consistency")

        # рутина
        if context.daily_routine:
            if any(x in context.daily_routine.lower() for x in ["chaos", "нет режима", "нерегулярно"]):
                signals.append("unstable_routine")

        # препятствия
        if context.main_obstacles:
            if len(context.main_obstacles) > 100:
                signals.append("high_friction")

        # мотивация
        if context.motivation:
            if len(context.motivation) < 30:
                signals.append("weak_motivation")

        # итоговая логика
        profile = {
            "signals": signals,
            "strategy": self._derive_strategy(signals),
        }

        return str(profile)

    def _derive_strategy(self, signals: list[str]) -> dict:
        """
        Превращаем сигналы в стратегию
        """

        strategy = {
            "task_load": "normal",
            "complexity": "normal",
            "focus": "balanced",
        }

        if "low_time" in signals:
            strategy["task_load"] = "low"
            strategy["complexity"] = "low"

        if "low_consistency" in signals:
            strategy["focus"] = "adherence"
            strategy["task_load"] = "low"

        if "unstable_routine" in signals:
            strategy["focus"] = "stability"
            strategy["complexity"] = "low"

        if "high_friction" in signals:
            strategy["task_load"] = "minimal"

        return strategy

    # =========================================================
    # 🔁 GENERATION
    # =========================================================

    async def _generate_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_language: str,
    ) -> AIPlanResponseV2:
        try:
            raw = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._parse_and_validate_ai_response(raw)
        except Exception as e:
            retry_prompt = self._build_retry_user_prompt(
                original_user_prompt=user_prompt,
                response_language=response_language,
            )

            raw = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
            )
            return self._parse_and_validate_ai_response(raw)
            # =========================================================
    # 🧠 PARSING + VALIDATION
    # =========================================================

    def _parse_and_validate_ai_response(self, raw_response: Any) -> AIPlanResponseV2:
        payload = self._normalize_ai_response_payload(raw_response)
        ai_response = AIPlanResponseV2.model_validate(payload)
        self._validate_ai_response(ai_response)
        return ai_response

    def _normalize_ai_response_payload(self, raw_response: Any) -> dict[str, Any]:
        if hasattr(raw_response, "model_dump"):
            payload = raw_response.model_dump()
        elif isinstance(raw_response, dict):
            payload = dict(raw_response)
        else:
            raise AIResponseValidationError("ai_response_not_a_dict")

        payload["summary"] = self._safe_text(payload.get("summary"))
        payload["duration_weeks"] = self._normalize_positive_int(
            payload.get("duration_weeks"), 4
        )
        payload["steps"] = self._normalize_steps(payload.get("steps"))
        payload["tasks"] = self._normalize_tasks(payload.get("tasks"))

        return payload

    # =========================================================
    # 🧩 NORMALIZATION
    # =========================================================

    def _normalize_steps(self, raw_steps: Any) -> list[dict[str, str]]:
        if not isinstance(raw_steps, list):
            return []

        result = []
        for item in raw_steps:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled step"
            desc = self._safe_text(item.get("description")) or "Execute this phase."

            result.append({"title": title, "description": desc})

        return result

    def _normalize_tasks(self, raw_tasks: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_tasks, list):
            return []

        result = []

        for item in raw_tasks:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled task"
            description = self._safe_text(item.get("description")) or "Do the action."

            cadence_type = self._normalize_cadence_type(item.get("cadence_type"))
            cadence_config = self._normalize_cadence_config(
                cadence_type,
                item.get("cadence_config"),
            )

            proof_type = self._normalize_proof_type(item.get("proof_type"))
            proof_required = self._normalize_bool(item.get("proof_required"), True)

            proof_prompt = self._normalize_proof_prompt(
                raw_prompt=item.get("proof_prompt"),
                title=title,
                description=description,
                proof_type=proof_type,
                proof_required=proof_required,
            )

            result.append(
                {
                    "title": title,
                    "description": description,
                    "cadence_type": cadence_type,
                    "cadence_config": cadence_config,
                    "proof_type": proof_type,
                    "proof_required": proof_required,
                    "proof_prompt": proof_prompt,
                }
            )

        return result

    # =========================================================
    # ⚙️ HELPERS
    # =========================================================

    def _normalize_cadence_type(self, value: Any) -> str:
        value = self._safe_text(value)
        if not value:
            return "daily"

        value = value.lower()

        if value in self.ALLOWED_CADENCE_TYPES:
            return value

        return "daily"

    def _normalize_cadence_config(self, cadence_type: str, raw: Any) -> dict:
        if cadence_type == "daily":
            return {}

        if not isinstance(raw, dict):
            raw = {}

        if cadence_type == "weekly":
            count = raw.get("times_per_week") or 3
            return {"times_per_week": max(1, min(int(count), 7))}

        if cadence_type == "specific_weekdays":
            days = raw.get("days_of_week") or [1, 3, 5]
            return {"days_of_week": [int(x) for x in days if 1 <= int(x) <= 7]}

        return {}

    def _normalize_proof_type(self, value: Any) -> str:
        value = self._safe_text(value)
        if not value:
            return "text"

        value = value.lower()

        if value in self.ALLOWED_PROOF_TYPES:
            return value

        return "text"

    def _normalize_proof_prompt(
        self,
        *,
        raw_prompt: Any,
        title: str,
        description: str,
        proof_type: str,
        proof_required: bool,
    ) -> str | None:
        if not proof_required:
            return None

        prompt = self._safe_text(raw_prompt)
        if prompt:
            return prompt

        return f"Подтверди выполнение: {title}"

    def _normalize_positive_int(self, value: Any, default: int) -> int:
        try:
            val = int(value)
            return val if val > 0 else default
        except Exception:
            return default

    def _normalize_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        return str(value).lower() in ["true", "1", "yes"]

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None

        text = str(value).strip()
        return text if text else None

    # =========================================================
    # 🧠 VALIDATION
    # =========================================================

    def _validate_ai_response(self, ai: AIPlanResponseV2) -> None:
        if not ai.summary:
            raise AIResponseValidationError("empty_summary")

        if len(ai.steps) < 3:
            raise AIResponseValidationError("too_few_steps")

        if len(ai.tasks) < 2:
            raise AIResponseValidationError("too_few_tasks")

    # =========================================================
    # 🧱 PLAN BUILDING
    # =========================================================

    def _map_to_plan_payload(self, *, goal_id: str, ai_response: AIPlanResponseV2):
        return {
            "title": "Execution plan",
            "summary": ai_response.summary,
            "content": {
                "duration_weeks": ai_response.duration_weeks,
                "steps": ai_response.steps,
                "tasks": ai_response.tasks,
            },
            "status": "draft",
        }

    # =========================================================
    # 📦 CONTEXT LOADING
    # =========================================================

    async def _load_context(self, goal_id: str) -> GoalGenerationContext:
        with engine.begin() as conn:
            goal = conn.execute(
                text("SELECT * FROM goals WHERE id = :id"),
                {"id": goal_id},
            ).mappings().first()

            if not goal:
                raise GoalNotFoundError()

            session = conn.execute(
                text("SELECT * FROM goal_sessions WHERE goal_id = :id"),
                {"id": goal_id},
            ).mappings().first()

            if not session:
                raise ProfilingIncompleteError()

            ctx = session.get("context_json") or {}
            profiling = ctx.get("profiling", {})

            return GoalGenerationContext(
                goal_id=str(goal["id"]),
                user_id=str(goal["user_id"]),
                goal_title=goal.get("title"),
                goal_description=goal.get("description"),
                current_level=profiling.get("summary", {}).get("current_state"),
                constraints=profiling.get("summary", {}).get("constraints"),
                resources=profiling.get("summary", {}).get("resources"),
                motivation=profiling.get("summary", {}).get("motivation"),
                coach_style=profiling.get("summary", {}).get("coach_style"),
                goal_outcome=profiling.get("summary", {}).get("goal_outcome"),
                deadline=goal.get("target_date"),
                time_budget=profiling.get("summary", {}).get("time_budget"),
                past_attempts=profiling.get("summary", {}).get("past_attempts"),
                main_obstacles=profiling.get("summary", {}).get("main_obstacles"),
                daily_routine=profiling.get("summary", {}).get("daily_routine"),
                planning_notes=None,
                plan_confidence=None,
                profiling_summary=profiling.get("summary"),
                profiling_answers=profiling.get("answers"),
            )

    def _validate_context(self, context: GoalGenerationContext):
        if not context.coach_style:
            raise ProfilingIncompleteError("coach_style_missing")

    # =========================================================
    # 🌍 LANGUAGE
    # =========================================================

    def _infer_response_language(self, context: GoalGenerationContext) -> str:
        text = f"{context.goal_title} {context.goal_description}"

        if re.search(r"[А-Яа-я]", text or ""):
            return "Russian"

        return "English"

    # =========================================================
    # 🔁 RETRY PROMPT
    # =========================================================

    def _build_retry_user_prompt(self, original_user_prompt: str, response_language: str) -> str:
        return f"""
Fix your previous response.

STRICT:
- JSON only
- no text outside JSON
- valid structure
- 4-6 steps
- 3-7 tasks
- no fluff
- language: {response_language}

Original:
{original_user_prompt}
"""