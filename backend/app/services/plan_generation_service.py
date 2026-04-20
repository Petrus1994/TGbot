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

    PROOF_TYPE_ALIASES = {
        "video": "file",
        "audio": "file",
        "voice": "file",
        "voice_note": "file",
        "document": "file",
        "pdf": "file",
        "image": "photo",
        "picture": "photo",
        "img": "photo",
        "screen": "screenshot",
        "attachment": "file",
    }

    CADENCE_TYPE_ALIASES = {
        "every_day": "daily",
        "everyday": "daily",
        "each_day": "daily",
        "weekdays": "specific_weekdays",
        "weekday": "specific_weekdays",
        "specific_days": "specific_weekdays",
        "days_of_week": "specific_weekdays",
        "certain_days": "specific_weekdays",
        "x_per_week": "weekly",
        "times_per_week": "weekly",
    }

    WEEKDAY_NAME_TO_INT = {
        "monday": 1,
        "mon": 1,
        "tuesday": 2,
        "tue": 2,
        "tues": 2,
        "wednesday": 3,
        "wed": 3,
        "thursday": 4,
        "thu": 4,
        "thur": 4,
        "thurs": 4,
        "friday": 5,
        "fri": 5,
        "saturday": 6,
        "sat": 6,
        "sunday": 7,
        "sun": 7,
        "понедельник": 1,
        "пн": 1,
        "вторник": 2,
        "вт": 2,
        "среда": 3,
        "ср": 3,
        "четверг": 4,
        "чт": 4,
        "пятница": 5,
        "пт": 5,
        "суббота": 6,
        "сб": 6,
        "воскресенье": 7,
        "вс": 7,
    }

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
    # MAIN ENTRY
    # =========================================================

    async def generate_plan(self, goal_id: str, regenerate: bool = False):
        if not settings.ai_plan_generation_enabled:
            raise AIPlanGenerationError("ai_plan_generation_disabled")

        context = await self._load_context(goal_id)
        self._validate_context(context)

        execution_profile = self._build_execution_profile(context)
        response_language = self._infer_response_language(context)

        system_prompt = self.prompt_builder.build_system_prompt(context)
        user_prompt = self.prompt_builder.build_user_prompt(context)

        user_prompt = f"""{user_prompt}

========================================
EXECUTION PROFILE (CRITICAL)
========================================
{execution_profile}

Use this to adapt the plan:
- simplify if needed
- reduce overload
- increase adherence
- avoid known failure patterns
- keep only high-leverage recurring tasks

========================================
LANGUAGE RULE
========================================
Return all user-facing content strictly in {response_language}.

This includes:
- summary
- step titles
- step descriptions
- task titles
- task descriptions
- proof prompts

Do not mix languages.

========================================
PROOF RULES
========================================
Proof must be:
- easy
- fast
- believable
- lightweight

Do not require full process recording.
Do not require excessive reporting.
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
    # EXECUTION INTELLIGENCE
    # =========================================================

    def _build_execution_profile(self, context: GoalGenerationContext) -> str:
        signals: list[str] = []

        time_budget = (context.time_budget or "").lower()
        past_attempts = (context.past_attempts or "").lower()
        daily_routine = (context.daily_routine or "").lower()
        main_obstacles = (context.main_obstacles or "").lower()
        motivation = (context.motivation or "").lower()

        if time_budget:
            if any(x in time_budget for x in ["1", "2", "30 min", "45 min", "час", "минут"]):
                signals.append("limited_time")
            else:
                signals.append("normal_time")

        if past_attempts:
            if any(x in past_attempts for x in ["fail", "failed", "quit", "брос", "не получилось", "срывал"]):
                signals.append("low_consistency")

        if daily_routine:
            if any(x in daily_routine for x in ["chaos", "chaotic", "нерегуляр", "нет режима", "плава", "unstable"]):
                signals.append("unstable_routine")

        if main_obstacles:
            if len(main_obstacles) > 120:
                signals.append("high_friction")
            if any(x in main_obstacles for x in ["устал", "fatigue", "tired", "energy", "энерг"]):
                signals.append("energy_constraint")
            if any(x in main_obstacles for x in ["отклады", "procrast", "avoid"]):
                signals.append("procrastination_risk")

        if motivation:
            if len(motivation) < 30:
                signals.append("weak_motivation")
            else:
                signals.append("meaningful_motivation")

        strategy = self._derive_strategy(signals)

        profile = {
            "signals": signals,
            "strategy": strategy,
        }
        return str(profile)

    def _derive_strategy(self, signals: list[str]) -> dict[str, str]:
        strategy = {
            "task_load": "normal",
            "complexity": "normal",
            "focus": "balanced",
            "progression": "steady",
        }

        if "limited_time" in signals:
            strategy["task_load"] = "low"
            strategy["complexity"] = "low"

        if "low_consistency" in signals:
            strategy["focus"] = "adherence"
            strategy["task_load"] = "low"
            strategy["progression"] = "gradual"

        if "unstable_routine" in signals:
            strategy["focus"] = "stability"
            strategy["complexity"] = "low"

        if "high_friction" in signals:
            strategy["task_load"] = "minimal"

        if "energy_constraint" in signals:
            strategy["complexity"] = "low"

        if "procrastination_risk" in signals:
            strategy["focus"] = "low-friction-starts"

        return strategy

    # =========================================================
    # GENERATION
    # =========================================================

    async def _generate_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_language: str,
    ) -> AIPlanResponseV2:
        first_error: Exception | None = None

        try:
            raw = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._parse_and_validate_ai_response(raw)
        except Exception as e:
            first_error = e

        retry_prompt = self._build_retry_user_prompt(
            original_user_prompt=user_prompt,
            response_language=response_language,
        )

        try:
            raw = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=retry_prompt,
            )
            return self._parse_and_validate_ai_response(raw)
        except Exception as retry_error:
            raise AIPlanGenerationError(
                f"ai_generation_failed_after_retry | first_error={first_error} | retry_error={retry_error}"
            ) from retry_error

    # =========================================================
    # PARSING + VALIDATION
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
            payload.get("duration_weeks"),
            default=4,
        )
        payload["steps"] = self._normalize_steps(payload.get("steps"))
        payload["tasks"] = self._normalize_tasks(payload.get("tasks"))

        return payload

    # =========================================================
    # NORMALIZATION
    # =========================================================

    def _normalize_steps(self, raw_steps: Any) -> list[dict[str, str]]:
        if not isinstance(raw_steps, list):
            return []

        result: list[dict[str, str]] = []

        for item in raw_steps:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled step"
            desc = self._safe_text(item.get("description")) or "Execute this phase."

            result.append(
                {
                    "title": title,
                    "description": desc,
                }
            )

        return result

    def _normalize_tasks(self, raw_tasks: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_tasks, list):
            return []

        result: list[dict[str, Any]] = []

        for item in raw_tasks:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled task"
            description = self._safe_text(item.get("description")) or "Do the action."

            cadence_type = self._normalize_cadence_type(item.get("cadence_type"))
            cadence_config = self._normalize_cadence_config(
                cadence_type=cadence_type,
                raw=item.get("cadence_config"),
                raw_task=item,
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
    # HELPERS
    # =========================================================

    def _normalize_cadence_type(self, value: Any) -> str:
        text_value = self._safe_text(value)
        if not text_value:
            return "daily"

        normalized = text_value.lower().strip()
        normalized = self.CADENCE_TYPE_ALIASES.get(normalized, normalized)

        if normalized in self.ALLOWED_CADENCE_TYPES:
            return normalized

        return "daily"

    def _normalize_cadence_config(
        self,
        *,
        cadence_type: str,
        raw: Any,
        raw_task: dict[str, Any],
    ) -> dict[str, Any]:
        config = raw if isinstance(raw, dict) else {}

        if cadence_type == "daily":
            return {}

        if cadence_type == "weekly":
            count = (
                config.get("times_per_week")
                or config.get("count")
                or raw_task.get("times_per_week")
                or 3
            )
            normalized_count = max(1, min(self._normalize_positive_int(count, 3), 7))
            return {"times_per_week": normalized_count}

        if cadence_type == "specific_weekdays":
            raw_days = (
                config.get("days_of_week")
                or config.get("weekdays")
                or raw_task.get("days_of_week")
                or raw_task.get("weekdays")
            )
            normalized_days = self._normalize_days_of_week(raw_days)
            if not normalized_days:
                normalized_days = [1, 3, 5]
            return {"days_of_week": normalized_days}

        return {}

    def _normalize_days_of_week(self, raw_days: Any) -> list[int]:
        if raw_days is None:
            return []

        values = raw_days if isinstance(raw_days, list) else [raw_days]
        result: list[int] = []

        for item in values:
            day_num = self._normalize_single_weekday(item)
            if day_num is not None:
                result.append(day_num)

        return sorted(set(x for x in result if 1 <= x <= 7))

    def _normalize_single_weekday(self, value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None

        if isinstance(value, int):
            if 1 <= value <= 7:
                return value
            if 0 <= value <= 6:
                return 7 if value == 0 else value
            return None

        text_value = self._safe_text(value)
        if not text_value:
            return None

        lowered = text_value.lower()

        if lowered in self.WEEKDAY_NAME_TO_INT:
            return self.WEEKDAY_NAME_TO_INT[lowered]

        digits = re.findall(r"\d+", lowered)
        if digits:
            num = int(digits[0])
            if 1 <= num <= 7:
                return num
            if 0 <= num <= 6:
                return 7 if num == 0 else num

        return None

    def _normalize_proof_type(self, value: Any) -> str:
        text_value = self._safe_text(value)
        if not text_value:
            return "text"

        normalized = text_value.lower().strip()
        normalized = self.PROOF_TYPE_ALIASES.get(normalized, normalized)

        if normalized in self.ALLOWED_PROOF_TYPES:
            return normalized

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

        combined = f"{title} {description}".lower()

        reading_keywords = [
            "read", "reading", "book", "chapter", "pages",
            "читать", "прочитать", "книга", "страниц", "глава",
        ]
        workout_keywords = [
            "workout", "exercise", "training", "gym", "run", "cardio",
            "трениров", "упражн", "зал", "бег", "кардио",
        ]
        coding_keywords = [
            "code", "coding", "script", "debug", "fix", "python", "backend", "frontend",
            "код", "скрипт", "программ", "разработ", "исправ",
        ]
        writing_keywords = [
            "write", "writing", "draft", "post", "article", "essay",
            "писать", "текст", "статья", "пост", "черновик",
        ]

        if any(k in combined for k in reading_keywords):
            return "Сфотографируй страницу или разворот, на котором остановился, чтобы было видно прогресс."

        if any(k in combined for k in workout_keywords):
            if proof_type == "photo":
                return "Сделай фото в контексте тренировки: зал, пробежка, форма или одно из упражнений."
            return "Коротко напиши, что именно сделал: упражнения, повторения, подходы или длительность."

        if any(k in combined for k in coding_keywords):
            return "Пришли скрин кода, редактора, коммита или результата запуска."

        if any(k in combined for k in writing_keywords):
            if proof_type == "screenshot":
                return "Пришли скрин текста или черновика, чтобы было видно результат."
            return "Отправь короткий фрагмент написанного или 1–2 предложения, что именно завершил."

        if proof_type == "photo":
            return f"Сделай простое фото, подтверждающее выполнение задачи: {title}."
        if proof_type == "screenshot":
            return f"Пришли скрин, где видно результат по задаче: {title}."
        if proof_type == "file":
            return f"Прикрепи файл или материал, подтверждающий выполнение задачи: {title}."

        return f"Коротко подтверди выполнение задачи: {title}."

    def _normalize_positive_int(self, value: Any, default: int) -> int:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def _normalize_bool(self, value: Any, default: bool) -> bool:
        if isinstance(value, bool):
            return value

        if value is None:
            return default

        return str(value).strip().lower() in {"true", "1", "yes", "y"}

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value).strip()
        return text_value or None

    def _normalize_text_field(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return ", ".join(items) if items else None

        if isinstance(value, dict):
            parts: list[str] = []
            for key, item in value.items():
                key_str = str(key).strip()
                item_str = str(item).strip()
                if key_str and item_str:
                    parts.append(f"{key_str}: {item_str}")
            return "; ".join(parts) if parts else None

        normalized = str(value).strip()
        return normalized or None

    def _pick_first_non_empty(self, *values: Any) -> str | None:
        for value in values:
            normalized = self._normalize_text_field(value)
            if normalized:
                return normalized
        return None

    # =========================================================
    # VALIDATION
    # =========================================================

    def _validate_ai_response(self, ai: AIPlanResponseV2) -> None:
        if not ai.summary:
            raise AIResponseValidationError("empty_summary")

        if len(ai.steps) < 3:
            raise AIResponseValidationError("too_few_steps")

        if len(ai.tasks) < 2:
            raise AIResponseValidationError("too_few_tasks")

        for step in ai.steps:
            text_to_check = f"{step.title} {step.description}".lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"forbidden_phrase_in_step: {phrase}"
                    )

        for task in ai.tasks:
            text_to_check = f"{task.title} {task.description}".lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"forbidden_phrase_in_task: {phrase}"
                    )

    def _validate_context(self, context: GoalGenerationContext):
        if not context.coach_style:
            raise ProfilingIncompleteError("coach_style_missing")
        if not context.current_level:
            raise ProfilingIncompleteError("current_level_missing")
        if not context.constraints:
            raise ProfilingIncompleteError("constraints_missing")
        if not context.resources:
            raise ProfilingIncompleteError("resources_missing")
        if not context.motivation:
            raise ProfilingIncompleteError("motivation_missing")

    # =========================================================
    # PLAN BUILDING
    # =========================================================

    def _map_to_plan_payload(
        self,
        *,
        goal_id: str,
        ai_response: AIPlanResponseV2,
    ) -> dict[str, Any]:
        recurring_tasks = [
            {
                "task_id": f"{goal_id}-task-{index}",
                "title": task.title,
                "description": task.description,
                "cadence_type": task.cadence_type,
                "cadence_config": task.cadence_config,
                "proof_type": task.proof_type,
                "proof_required": task.proof_required,
                "proof_prompt": getattr(task, "proof_prompt", None),
                "order": index,
            }
            for index, task in enumerate(ai_response.tasks, start=1)
        ]

        days = self._build_daily_days(ai_response=ai_response)

        content = {
            "duration_weeks": ai_response.duration_weeks,
            "milestones": [step.title for step in ai_response.steps],
            "steps": [
                {
                    "step_id": f"{goal_id}-step-{index}",
                    "title": step.title,
                    "description": step.description,
                    "order": index,
                }
                for index, step in enumerate(ai_response.steps, start=1)
            ],
            "tasks": recurring_tasks,
            "days": days,
        }

        return {
            "title": "Execution plan",
            "summary": ai_response.summary,
            "content": content,
            "status": "draft",
        }

    def _build_daily_days(self, ai_response: AIPlanResponseV2) -> list[dict[str, Any]]:
        total_days = max(7, ai_response.duration_weeks * 7)
        start_date = date.today()
        steps = ai_response.steps
        tasks = ai_response.tasks

        days: list[dict[str, Any]] = []

        for day_number in range(1, total_days + 1):
            planned_date = start_date + timedelta(days=day_number - 1)
            weekday = planned_date.isoweekday()

            step = self._pick_step_for_day(
                steps=steps,
                day_number=day_number,
                total_days=total_days,
            )

            day_tasks: list[dict[str, Any]] = []

            for task in tasks:
                if self._task_is_scheduled_for_day(
                    task=task,
                    day_number=day_number,
                    weekday=weekday,
                ):
                    day_tasks.append(
                        {
                            "title": task.title,
                            "objective": None,
                            "description": task.description,
                            "instructions": task.description,
                            "why_today": None,
                            "success_criteria": None,
                            "estimated_minutes": None,
                            "detail_level": 1,
                            "bucket": "must",
                            "priority": "medium",
                            "is_required": True,
                            "proof_required": task.proof_required,
                            "recommended_proof_type": task.proof_type,
                            "proof_prompt": getattr(task, "proof_prompt", None),
                            "task_type": None,
                            "difficulty": None,
                            "tips": [],
                            "technique_cues": [],
                            "common_mistakes": [],
                            "steps": [],
                            "resources": [],
                        }
                    )

            if not day_tasks and tasks:
                fallback_task = tasks[0]
                day_tasks.append(
                    {
                        "title": fallback_task.title,
                        "objective": None,
                        "description": fallback_task.description,
                        "instructions": fallback_task.description,
                        "why_today": None,
                        "success_criteria": None,
                        "estimated_minutes": None,
                        "detail_level": 1,
                        "bucket": "must",
                        "priority": "medium",
                        "is_required": True,
                        "proof_required": fallback_task.proof_required,
                        "recommended_proof_type": fallback_task.proof_type,
                        "proof_prompt": getattr(fallback_task, "proof_prompt", None),
                        "task_type": None,
                        "difficulty": None,
                        "tips": [],
                        "technique_cues": [],
                        "common_mistakes": [],
                        "steps": [],
                        "resources": [],
                    }
                )

            days.append(
                {
                    "day_number": day_number,
                    "focus": step.title,
                    "summary": step.description,
                    "headline": None,
                    "focus_message": None,
                    "main_task_title": day_tasks[0]["title"] if day_tasks else None,
                    "total_estimated_minutes": None,
                    "planned_date": planned_date.isoformat(),
                    "tasks": day_tasks,
                }
            )

        return days

    def _pick_step_for_day(self, *, steps, day_number: int, total_days: int):
        if not steps:
            raise AIResponseValidationError("ai_response_steps_empty")

        block_size = max(1, total_days // len(steps))
        index = min((day_number - 1) // block_size, len(steps) - 1)
        return steps[index]

    def _task_is_scheduled_for_day(self, *, task, day_number: int, weekday: int) -> bool:
        if task.cadence_type == "daily":
            return True

        if task.cadence_type == "specific_weekdays":
            days_of_week = task.cadence_config.get("days_of_week", [])
            return weekday in days_of_week

        if task.cadence_type == "weekly":
            times_per_week = task.cadence_config.get("times_per_week", 1)
            scheduled_days = self._weekly_slots(times_per_week)
            return weekday in scheduled_days

        return False

    def _weekly_slots(self, times_per_week: int) -> set[int]:
        normalized = max(1, min(int(times_per_week), 7))
        presets: dict[int, set[int]] = {
            1: {1},
            2: {2, 5},
            3: {1, 3, 5},
            4: {1, 2, 4, 6},
            5: {1, 2, 3, 5, 6},
            6: {1, 2, 3, 4, 5, 6},
            7: {1, 2, 3, 4, 5, 6, 7},
        }
        return presets[normalized]

    # =========================================================
    # CONTEXT LOADING
    # =========================================================

    async def _load_context(self, goal_id: str) -> GoalGenerationContext:
        with engine.begin() as conn:
            goal = conn.execute(
                text(
                    """
                    SELECT id, user_id, title, description, target_date, status
                    FROM goals
                    WHERE id = :id
                    """
                ),
                {"id": goal_id},
            ).mappings().first()

            if not goal:
                raise GoalNotFoundError("goal_not_found")

            session = conn.execute(
                text(
                    """
                    SELECT goal_id, state, substate, context_json
                    FROM goal_sessions
                    WHERE goal_id = :id
                    """
                ),
                {"id": goal_id},
            ).mappings().first()

            if not session:
                raise ProfilingIncompleteError("profiling_not_started")

            context_json = session.get("context_json") or {}
            if not isinstance(context_json, dict):
                context_json = {}

            profiling = context_json.get("profiling", {})
            if not isinstance(profiling, dict):
                profiling = {}

            profiling_summary = profiling.get("summary", {})
            if not isinstance(profiling_summary, dict):
                profiling_summary = {}

            profiling_answers = profiling.get("answers", {})
            if not isinstance(profiling_answers, dict):
                profiling_answers = {}

            current_level = self._pick_first_non_empty(
                profiling_summary.get("current_state"),
                profiling_summary.get("current_level"),
                profiling_answers.get("current_state"),
                profiling_answers.get("current_level"),
            )
            constraints = self._pick_first_non_empty(
                profiling_summary.get("constraints"),
                profiling_answers.get("constraints"),
            )
            resources = self._pick_first_non_empty(
                profiling_summary.get("resources"),
                profiling_answers.get("resources"),
            )
            motivation = self._pick_first_non_empty(
                profiling_summary.get("motivation"),
                profiling_answers.get("motivation"),
            )
            coach_style = self._pick_first_non_empty(
                profiling_summary.get("coach_style"),
                profiling_answers.get("coach_style"),
                profiling_summary.get("preferred_execution_style"),
                profiling_answers.get("preferred_execution_style"),
            )
            goal_outcome = self._pick_first_non_empty(
                profiling_summary.get("goal_outcome"),
                profiling_summary.get("success_metrics"),
                profiling_answers.get("goal_outcome"),
            )
            deadline = self._pick_first_non_empty(
                profiling_summary.get("deadline"),
                profiling_answers.get("deadline"),
                goal.get("target_date"),
            )
            time_budget = self._pick_first_non_empty(
                profiling_summary.get("time_budget"),
                profiling_answers.get("time_budget"),
            )
            past_attempts = self._pick_first_non_empty(
                profiling_summary.get("past_attempts"),
                profiling_answers.get("past_attempts"),
            )
            main_obstacles = self._pick_first_non_empty(
                profiling_summary.get("main_obstacles"),
                profiling_summary.get("risk_factors"),
                profiling_answers.get("main_obstacles"),
                profiling_answers.get("obstacles"),
            )
            daily_routine = self._pick_first_non_empty(
                profiling_summary.get("daily_routine"),
                profiling_answers.get("daily_routine"),
            )
            planning_notes = self._pick_first_non_empty(
                profiling_summary.get("planning_notes"),
                profiling_summary.get("environment"),
                profiling_answers.get("planning_notes"),
                profiling_answers.get("environment"),
            )
            plan_confidence = self._pick_first_non_empty(
                profiling_summary.get("plan_confidence"),
            )

            return GoalGenerationContext(
                goal_id=str(goal["id"]),
                user_id=str(goal["user_id"]),
                goal_title=goal.get("title") or "Untitled goal",
                goal_description=goal.get("description"),
                current_level=current_level,
                constraints=constraints,
                resources=resources,
                motivation=motivation,
                coach_style=coach_style,
                goal_outcome=goal_outcome,
                deadline=deadline,
                time_budget=time_budget,
                past_attempts=past_attempts,
                main_obstacles=main_obstacles,
                daily_routine=daily_routine,
                planning_notes=planning_notes,
                plan_confidence=plan_confidence,
                profiling_summary=profiling_summary,
                profiling_answers=profiling_answers,
            )

    # =========================================================
    # LANGUAGE
    # =========================================================

    def _infer_response_language(self, context: GoalGenerationContext) -> str:
        text_value = " ".join(
            part
            for part in [
                context.goal_title,
                context.goal_description,
                context.current_level,
                context.constraints,
                context.resources,
                context.motivation,
                context.coach_style,
                context.goal_outcome,
                context.time_budget,
                context.main_obstacles,
                context.daily_routine,
            ]
            if part
        )

        if re.search(r"[А-Яа-яЁё]", text_value or ""):
            return "Russian"

        return "English"

    # =========================================================
    # RETRY PROMPT
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
- tasks must be concrete
- proof prompts must be easy and valid
- content language: {response_language}

Original:
{original_user_prompt}
""".strip()