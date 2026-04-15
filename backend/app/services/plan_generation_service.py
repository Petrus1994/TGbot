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
        "photo_text": "photo",
        "screen": "screenshot",
        "screen_recording": "file",
        "recording": "file",
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
        "eat healthy",
        "practice more",
        "stay consistent",
        "try your best",
        "stay motivated",
        "believe in yourself",
        "don't give up",
        "think positively",
        "just keep going",
        "keep pushing",
    ]

    def __init__(self) -> None:
        self.prompt_builder = PlanPromptBuilder()
        self.llm_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def generate_plan(self, goal_id: str, regenerate: bool = False):
        if not settings.ai_plan_generation_enabled:
            raise AIPlanGenerationError("ai_plan_generation_disabled")

        context = await self._load_context(goal_id)
        self._validate_context(context)

        response_language = self._infer_response_language(context)

        system_prompt = self.prompt_builder.build_system_prompt(context)
        user_prompt = self.prompt_builder.build_user_prompt(context)
        user_prompt = f"""{user_prompt}

IMPORTANT LANGUAGE RULE:
Return all user-facing content strictly in {response_language}.
This includes:
- summary
- step titles
- step descriptions
- task titles
- task descriptions
- proof prompts

Do not mix languages.

PROOF DESIGN RULES:
For every recurring task, provide:
- proof_required
- proof_type
- proof_prompt

Proofs must be EASY but VALID.
Do not require full process recording.
Use lightweight believable proofs.

Examples:
- Reading -> photo of current page/spread is enough
- Workout -> photo in workout context or short completion note is enough
- Coding -> screenshot of code/editor is enough
- Writing -> screenshot or pasted text is enough
- Learning app -> screenshot of lesson/progress is enough
- Planning/reflection -> short text summary is enough
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

    async def _generate_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_language: str,
    ) -> AIPlanResponseV2:
        first_error: Exception | None = None

        try:
            raw_response = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            return self._parse_and_validate_ai_response(raw_response)
        except Exception as e:
            first_error = e

        retry_user_prompt = self._build_retry_user_prompt(
            original_user_prompt=user_prompt,
            response_language=response_language,
        )

        try:
            raw_response = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=retry_user_prompt,
            )
            return self._parse_and_validate_ai_response(raw_response)
        except Exception as retry_error:
            raise AIPlanGenerationError(
                f"ai_generation_failed_after_retry | first_error={first_error} | retry_error={retry_error}"
            ) from retry_error

    def _parse_and_validate_ai_response(self, raw_response: Any) -> AIPlanResponseV2:
        normalized_payload = self._normalize_ai_response_payload(raw_response)
        ai_response = AIPlanResponseV2.model_validate(normalized_payload)
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
        payload["duration_weeks"] = self._normalize_duration_weeks(
            payload.get("duration_weeks")
        )
        payload["steps"] = self._normalize_steps(payload.get("steps"))
        payload["tasks"] = self._normalize_tasks(payload.get("tasks"))

        return payload

    def _normalize_steps(self, raw_steps: Any) -> list[dict[str, str]]:
        if not isinstance(raw_steps, list):
            return []

        normalized_steps: list[dict[str, str]] = []

        for item in raw_steps:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled step"
            description = self._safe_text(item.get("description")) or (
                "Complete the next meaningful phase for this goal."
            )

            normalized_steps.append(
                {
                    "title": title,
                    "description": description,
                }
            )

        return normalized_steps

    def _normalize_tasks(self, raw_tasks: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_tasks, list):
            return []

        normalized_tasks: list[dict[str, Any]] = []

        for item in raw_tasks:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or "Untitled task"
            description = self._safe_text(item.get("description")) or (
                "Do one concrete repeatable action that directly moves the goal forward."
            )

            cadence_type = self._normalize_cadence_type(item.get("cadence_type"))
            cadence_config = self._normalize_cadence_config(
                cadence_type=cadence_type,
                raw_config=item.get("cadence_config"),
                raw_task=item,
            )

            proof_type = self._normalize_proof_type(item.get("proof_type"))
            proof_required = self._normalize_bool(
                item.get("proof_required"),
                default=True,
            )
            proof_prompt = self._normalize_proof_prompt(
                raw_prompt=item.get("proof_prompt"),
                title=title,
                description=description,
                proof_type=proof_type,
                proof_required=proof_required,
            )

            normalized_tasks.append(
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

        return normalized_tasks

    def _normalize_cadence_type(self, raw_value: Any) -> str:
        value = self._safe_text(raw_value)
        if not value:
            return "daily"

        value = value.strip().lower()
        value = self.CADENCE_TYPE_ALIASES.get(value, value)

        if value in self.ALLOWED_CADENCE_TYPES:
            return value

        return "daily"

    def _normalize_cadence_config(
        self,
        *,
        cadence_type: str,
        raw_config: Any,
        raw_task: dict[str, Any],
    ) -> dict[str, Any]:
        config = raw_config if isinstance(raw_config, dict) else {}

        if cadence_type == "daily":
            return {}

        if cadence_type == "weekly":
            times_per_week = (
                config.get("times_per_week")
                or config.get("count")
                or config.get("frequency")
                or raw_task.get("times_per_week")
            )

            normalized_times = self._normalize_positive_int(times_per_week, default=3)
            normalized_times = max(1, min(normalized_times, 7))

            return {"times_per_week": normalized_times}

        if cadence_type == "specific_weekdays":
            raw_days = (
                config.get("days_of_week")
                or config.get("weekdays")
                or config.get("days")
                or raw_task.get("days_of_week")
                or raw_task.get("weekdays")
            )

            normalized_days = self._normalize_days_of_week(raw_days)

            if not normalized_days:
                fallback_days = (
                    config.get("times_per_week")
                    or raw_task.get("times_per_week")
                )
                if fallback_days:
                    count = max(
                        1,
                        min(
                            self._normalize_positive_int(fallback_days, default=3),
                            7,
                        ),
                    )
                    normalized_days = sorted(self._weekly_slots(count))
                else:
                    normalized_days = [1, 3, 5]

            return {"days_of_week": normalized_days}

        return {}

    def _normalize_days_of_week(self, raw_days: Any) -> list[int]:
        if raw_days is None:
            return []

        values: list[Any]
        if isinstance(raw_days, list):
            values = raw_days
        else:
            values = [raw_days]

        normalized: list[int] = []

        for item in values:
            day_int = self._normalize_single_weekday(item)
            if day_int is not None:
                normalized.append(day_int)

        return sorted(set(day for day in normalized if 1 <= day <= 7))

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

    def _normalize_proof_type(self, raw_value: Any) -> str:
        value = self._safe_text(raw_value)
        if not value:
            return "text"

        value = value.strip().lower()
        value = self.PROOF_TYPE_ALIASES.get(value, value)

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

        return self._build_default_proof_prompt(
            title=title,
            description=description,
            proof_type=proof_type,
        )

    def _build_default_proof_prompt(
        self,
        *,
        title: str,
        description: str,
        proof_type: str,
    ) -> str:
        combined = f"{title} {description}".lower()

        reading_keywords = [
            "read",
            "reading",
            "book",
            "chapter",
            "pages",
            "страниц",
            "страницы",
            "книг",
            "книга",
            "читать",
            "прочитать",
            "глава",
        ]
        workout_keywords = [
            "workout",
            "exercise",
            "training",
            "gym",
            "run",
            "cardio",
            "squat",
            "push-up",
            "pull-up",
            "stretch",
            "трениров",
            "присед",
            "бег",
            "зал",
            "кардио",
            "упражн",
            "растяж",
        ]
        coding_keywords = [
            "code",
            "coding",
            "program",
            "repository",
            "repo",
            "app",
            "script",
            "debug",
            "fix",
            "develop",
            "python",
            "backend",
            "frontend",
            "код",
            "скрипт",
            "репозитор",
            "разработ",
            "программ",
            "дебаг",
            "исправ",
        ]
        writing_keywords = [
            "write",
            "writing",
            "draft",
            "journal",
            "essay",
            "post",
            "article",
            "outline",
            "писать",
            "текст",
            "пост",
            "статья",
            "черновик",
            "заметка",
        ]
        app_learning_keywords = [
            "lesson",
            "duolingo",
            "course",
            "module",
            "quiz",
            "practice",
            "learn",
            "study app",
            "урок",
            "курс",
            "модуль",
            "квиз",
            "уроков",
        ]
        planning_keywords = [
            "plan",
            "planning",
            "reflect",
            "reflection",
            "review",
            "analyze",
            "journal",
            "план",
            "рефлек",
            "разбор",
            "анализ",
            "отчет",
            "итоги",
        ]

        if any(keyword in combined for keyword in reading_keywords):
            return (
                "Сфотографируй страницу или разворот, на котором остановился, "
                "чтобы было видно реальный прогресс по чтению."
            )

        if any(keyword in combined for keyword in workout_keywords):
            if proof_type == "photo":
                return (
                    "Сделай фото в контексте тренировки: в форме, в зале, на пробежке "
                    "или во время одного из упражнений."
                )
            return (
                "Кратко напиши, что именно сделал: упражнение, количество повторений "
                "или длительность тренировки."
            )

        if any(keyword in combined for keyword in coding_keywords):
            return (
                "Пришли скрин редактора, кода, коммита или результата запуска, "
                "чтобы был виден конкретный прогресс."
            )

        if any(keyword in combined for keyword in writing_keywords):
            if proof_type == "screenshot":
                return (
                    "Пришли скрин текста, заметки или черновика, чтобы было видно, "
                    "что работа реально сделана."
                )
            return (
                "Отправь 1–3 предложения из написанного или коротко опиши, "
                "что именно закончил."
            )

        if any(keyword in combined for keyword in app_learning_keywords):
            return (
                "Пришли скрин урока, прогресса или завершенного блока в приложении."
            )

        if any(keyword in combined for keyword in planning_keywords):
            return (
                "Напиши короткий конкретный итог: что решил, что запланировал "
                "или какой вывод сделал."
            )

        if proof_type == "photo":
            return (
                "Сделай простое фото, которое показывает контекст выполнения задачи."
            )
        if proof_type == "screenshot":
            return (
                "Пришли скрин, на котором видно результат или прогресс по задаче."
            )
        if proof_type == "file":
            return (
                "Прикрепи файл или материал, который подтверждает выполнение задачи."
            )

        return (
            "Коротко напиши, что именно сделал и какой конкретный результат получил."
        )

    def _normalize_duration_weeks(self, raw_value: Any) -> int:
        normalized = self._normalize_positive_int(raw_value, default=4)
        return max(1, normalized)

    def _normalize_positive_int(self, raw_value: Any, default: int) -> int:
        if raw_value is None or isinstance(raw_value, bool):
            return default

        if isinstance(raw_value, int):
            return raw_value if raw_value > 0 else default

        try:
            parsed = int(str(raw_value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def _normalize_bool(self, raw_value: Any, default: bool) -> bool:
        if isinstance(raw_value, bool):
            return raw_value

        if raw_value is None:
            return default

        text_value = str(raw_value).strip().lower()
        if text_value in {"true", "1", "yes", "y"}:
            return True
        if text_value in {"false", "0", "no", "n"}:
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

    async def _load_context(self, goal_id: str) -> GoalGenerationContext:
        with engine.begin() as connection:
            goal = connection.execute(
                text(
                    """
                    SELECT id, user_id, title, description, target_date, status
                    FROM goals
                    WHERE id = :goal_id
                    """
                ),
                {"goal_id": goal_id},
            ).mappings().first()

            if not goal:
                raise GoalNotFoundError("goal_not_found")

            session = connection.execute(
                text(
                    """
                    SELECT goal_id, state, substate, context_json
                    FROM goal_sessions
                    WHERE goal_id = :goal_id
                    """
                ),
                {"goal_id": goal_id},
            ).mappings().first()

            if not session:
                raise ProfilingIncompleteError("profiling_not_started")

            context_json = session["context_json"] or {}
            if not isinstance(context_json, dict):
                context_json = {}

            profiling = context_json.get("profiling", {})
            if not isinstance(profiling, dict):
                profiling = {}

            profiling_summary = profiling.get("summary", {})
            if not isinstance(profiling_summary, dict):
                profiling_summary = {}

            answers = profiling.get("answers", {})
            if not isinstance(answers, dict):
                answers = {}

            current_level = self._pick_first_non_empty(
                profiling_summary.get("current_state"),
                profiling_summary.get("current_level"),
                answers.get("current_state"),
                answers.get("current_level"),
            )
            constraints = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("constraints"),
                    answers.get("constraints"),
                )
            )
            resources = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("resources"),
                    answers.get("resources"),
                )
            )
            motivation = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("motivation"),
                    answers.get("motivation"),
                )
            )
            coach_style = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("coach_style"),
                    answers.get("coach_style"),
                    profiling_summary.get("preferred_execution_style"),
                    answers.get("preferred_execution_style"),
                )
            )

            goal_outcome = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("goal_outcome"),
                    profiling_summary.get("success_metrics"),
                    answers.get("goal_outcome"),
                )
            )
            deadline = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("deadline"),
                    answers.get("deadline"),
                    goal.get("target_date"),
                )
            )
            time_budget = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("time_budget"),
                    answers.get("time_budget"),
                )
            )
            past_attempts = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("past_attempts"),
                    answers.get("past_attempts"),
                )
            )
            main_obstacles = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("main_obstacles"),
                    profiling_summary.get("risk_factors"),
                    answers.get("main_obstacles"),
                    answers.get("obstacles"),
                )
            )
            daily_routine = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("daily_routine"),
                    answers.get("daily_routine"),
                )
            )
            planning_notes = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("planning_notes"),
                    profiling_summary.get("environment"),
                    answers.get("planning_notes"),
                    answers.get("environment"),
                )
            )
            plan_confidence = self._normalize_text_field(
                self._pick_first_non_empty(
                    profiling_summary.get("plan_confidence"),
                )
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
                profiling_answers=answers,
            )

    def _validate_context(self, context: GoalGenerationContext) -> None:
        missing_fields: list[str] = []

        if not context.current_level:
            missing_fields.append("current_level")
        if not context.constraints:
            missing_fields.append("constraints")
        if not context.resources:
            missing_fields.append("resources")
        if not context.motivation:
            missing_fields.append("motivation")
        if not context.coach_style:
            missing_fields.append("coach_style")

        if missing_fields:
            print(f"❌ PLAN GENERATION MISSING FIELDS: {missing_fields}")
            print(f"❌ CONTEXT FOR PLAN GENERATION: {context.model_dump()}")
            raise ProfilingIncompleteError(
                f"profiling_incomplete: missing {', '.join(missing_fields)}"
            )

    def _validate_ai_response(self, ai_response: AIPlanResponseV2) -> None:
        steps = ai_response.steps
        tasks = ai_response.tasks

        if not 4 <= len(steps) <= 6:
            raise AIResponseValidationError("ai_response_must_contain_4_to_6_steps")

        if not 3 <= len(tasks) <= 7:
            raise AIResponseValidationError("ai_response_must_contain_3_to_7_tasks")

        if ai_response.duration_weeks < 1:
            raise AIResponseValidationError("ai_duration_weeks_invalid")

        if not ai_response.summary.strip():
            raise AIResponseValidationError("ai_summary_empty")

        for step in steps:
            if not step.title.strip():
                raise AIResponseValidationError("ai_step_title_empty")
            if not step.description.strip():
                raise AIResponseValidationError("ai_step_description_empty")

            text_to_check = f"{step.title} {step.description}".lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"ai_response_contains_forbidden_phrase: {phrase}"
                    )

        for task in tasks:
            if not task.title.strip():
                raise AIResponseValidationError("ai_task_title_empty")
            if not task.description.strip():
                raise AIResponseValidationError("ai_task_description_empty")

            text_to_check = f"{task.title} {task.description}".lower()
            for phrase in self.FORBIDDEN_PHRASES:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"ai_task_contains_forbidden_phrase: {phrase}"
                    )

            if task.cadence_type not in self.ALLOWED_CADENCE_TYPES:
                raise AIResponseValidationError(
                    f"ai_task_invalid_cadence_type: {task.cadence_type}"
                )

            if task.proof_type not in self.ALLOWED_PROOF_TYPES:
                raise AIResponseValidationError(
                    f"ai_task_invalid_proof_type: {task.proof_type}"
                )

            if task.cadence_type == "daily" and task.cadence_config != {}:
                raise AIResponseValidationError(
                    "ai_task_daily_cadence_config_must_be_empty"
                )

            if task.cadence_type == "weekly":
                times_per_week = task.cadence_config.get("times_per_week")
                if not isinstance(times_per_week, int) or times_per_week < 1:
                    raise AIResponseValidationError(
                        "ai_task_weekly_times_per_week_invalid"
                    )

            if task.cadence_type == "specific_weekdays":
                days_of_week = task.cadence_config.get("days_of_week")
                if not isinstance(days_of_week, list) or not days_of_week:
                    raise AIResponseValidationError("ai_task_days_of_week_invalid")
                if not all(isinstance(day, int) and 1 <= day <= 7 for day in days_of_week):
                    raise AIResponseValidationError("ai_task_days_of_week_out_of_range")

            proof_prompt = getattr(task, "proof_prompt", None)
            if task.proof_required and (not proof_prompt or not str(proof_prompt).strip()):
                raise AIResponseValidationError("ai_task_proof_prompt_empty")

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
            "title": "Personal goal execution plan",
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
                            "description": task.description,
                            "objective": None,
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
                        "description": fallback_task.description,
                        "objective": None,
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
            scheduled_weekdays = self._weekly_slots(times_per_week)
            return weekday in scheduled_weekdays

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

    def _infer_response_language(self, context: GoalGenerationContext) -> str:
        text_parts = [
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
        combined = " ".join(part for part in text_parts if part)

        if re.search(r"[А-Яа-яЁё]", combined):
            return "Russian"

        return "English"

    def _build_retry_user_prompt(self, original_user_prompt: str, response_language: str) -> str:
        return f"""
The previous answer was invalid.

You must fix it now.

Strict requirements:
- Return valid JSON only
- No markdown
- No code fences
- No explanations before or after JSON
- Exactly 4 to 6 strategic steps
- Exactly 3 to 7 recurring tasks
- Summary must be non-empty
- duration_weeks must be >= 1
- Steps must be concrete and actionable
- Tasks must be realistic and repeatable
- Tasks must not be generic
- Do not use motivational fluff
- All user-facing content must be strictly in {response_language}
- Do not mix languages
- Allowed cadence_type:
  - daily
  - weekly
  - specific_weekdays
- Allowed proof_type:
  - text
  - photo
  - screenshot
  - file
- Every task must contain proof_prompt
- Proofs must be easy but valid
- Do not require full process recording
- If cadence_type is daily -> cadence_config must be {{}}
- If cadence_type is weekly -> cadence_config must include integer times_per_week
- If cadence_type is specific_weekdays -> cadence_config must include days_of_week with integers from 1 to 7
- Do not use phrases like:
  - try your best
  - stay motivated
  - believe in yourself
  - don't give up
  - think positively
  - stay consistent
  - eat healthy
  - practice more
  - постарайся
  - думай
  - не сдавайся
  - верь в себя

Return JSON in this exact format:
{{
  "summary": "short strategic summary",
  "duration_weeks": 4,
  "steps": [
    {{
      "title": "step title",
      "description": "specific concrete action"
    }}
  ],
  "tasks": [
    {{
      "title": "task title",
      "description": "specific recurring action",
      "cadence_type": "daily",
      "cadence_config": {{}},
      "proof_type": "text",
      "proof_required": true,
      "proof_prompt": "very easy but valid proof instruction"
    }}
  ]
}}

Original task:
{original_user_prompt}
""".strip()

    def _pick_first_non_empty(self, *values):
        for value in values:
            normalized = self._normalize_text_field(value)
            if normalized:
                return normalized
        return None

    def _normalize_text_field(self, value):
        if value is None:
            return None

        if isinstance(value, list):
            items = [str(item).strip() for item in value if str(item).strip()]
            return ", ".join(items) if items else None

        if isinstance(value, dict):
            parts = []
            for key, item in value.items():
                key_str = str(key).strip()
                item_str = str(item).strip()
                if key_str and item_str:
                    parts.append(f"{key_str}: {item_str}")
            return "; ".join(parts) if parts else None

        value = str(value).strip()
        return value or None

    async def _fallback_stub(self, goal_id: str) -> dict:
        raise AIPlanGenerationError("fallback_should_be_handled_in_route")