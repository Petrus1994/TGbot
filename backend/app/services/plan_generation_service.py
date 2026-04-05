from __future__ import annotations

from datetime import date, timedelta
import re

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
from app.services.daily_task_detailing_service import DailyTaskDetailingService
from app.services.openai_client import OpenAIClient
from app.services.plan_prompt_builder import PlanPromptBuilder
from app.services.plan_service import save_generated_plan


class PlanGenerationService:
    def __init__(self) -> None:
        self.prompt_builder = PlanPromptBuilder()
        self.llm_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )
        self.daily_task_detailing_service = DailyTaskDetailingService()

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

Do not mix languages.
"""

        ai_response = await self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_language=response_language,
        )

        plan_payload = await self._map_to_plan_payload(
            goal_id=goal_id,
            ai_response=ai_response,
            context=context,
            response_language=response_language,
        )

        return save_generated_plan(
            goal_id=goal_id,
            title=plan_payload["title"],
            summary=plan_payload["summary"],
            content=plan_payload["content"],
            status=plan_payload["status"],
        )

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
            ai_response = AIPlanResponseV2.model_validate(raw_response)
            self._validate_ai_response(ai_response)
            return ai_response
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
            ai_response = AIPlanResponseV2.model_validate(raw_response)
            self._validate_ai_response(ai_response)
            return ai_response
        except Exception as retry_error:
            raise AIPlanGenerationError(
                f"ai_generation_failed_after_retry | first_error={first_error} | retry_error={retry_error}"
            ) from retry_error

    async def _load_context(self, goal_id: str) -> GoalGenerationContext:
        with engine.begin() as connection:
            goal = connection.execute(
                text(
                    """
                    SELECT id, user_id, title, description, status
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

        forbidden_phrases = [
            "постарайся",
            "думай",
            "верь в себя",
            "не сдавайся",
            "будь мотивирован",
            "try your best",
            "stay motivated",
            "believe in yourself",
            "don't give up",
            "think positively",
        ]

        if not ai_response.summary.strip():
            raise AIResponseValidationError("ai_summary_empty")

        for step in steps:
            if not step.title.strip():
                raise AIResponseValidationError("ai_step_title_empty")
            if not step.description.strip():
                raise AIResponseValidationError("ai_step_description_empty")

            text_to_check = f"{step.title} {step.description}".lower()
            for phrase in forbidden_phrases:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"ai_response_contains_forbidden_phrase: {phrase}"
                    )

        allowed_cadence_types = {"daily", "weekly", "specific_weekdays"}
        allowed_proof_types = {"text", "photo", "screenshot", "file"}

        for task in tasks:
            if not task.title.strip():
                raise AIResponseValidationError("ai_task_title_empty")
            if not task.description.strip():
                raise AIResponseValidationError("ai_task_description_empty")

            if task.cadence_type not in allowed_cadence_types:
                raise AIResponseValidationError(
                    f"ai_task_invalid_cadence_type: {task.cadence_type}"
                )

            if task.proof_type not in allowed_proof_types:
                raise AIResponseValidationError(
                    f"ai_task_invalid_proof_type: {task.proof_type}"
                )

            if task.cadence_type == "daily":
                if task.cadence_config != {}:
                    raise AIResponseValidationError("ai_task_daily_cadence_config_must_be_empty")

            if task.cadence_type == "weekly":
                times_per_week = task.cadence_config.get("times_per_week")
                if not isinstance(times_per_week, int) or times_per_week < 1:
                    raise AIResponseValidationError("ai_task_weekly_times_per_week_invalid")

            if task.cadence_type == "specific_weekdays":
                days_of_week = task.cadence_config.get("days_of_week")
                if not isinstance(days_of_week, list) or not days_of_week:
                    raise AIResponseValidationError("ai_task_days_of_week_invalid")
                if not all(isinstance(day, int) and 1 <= day <= 7 for day in days_of_week):
                    raise AIResponseValidationError("ai_task_days_of_week_out_of_range")

    async def _map_to_plan_payload(
        self,
        *,
        goal_id: str,
        ai_response: AIPlanResponseV2,
        context: GoalGenerationContext,
        response_language: str,
    ) -> dict:
        recurring_tasks = [
            {
                "task_id": f"{goal_id}-task-{index}",
                "title": task.title,
                "description": task.description,
                "cadence_type": task.cadence_type,
                "cadence_config": task.cadence_config,
                "proof_type": task.proof_type,
                "proof_required": task.proof_required,
                "order": index,
            }
            for index, task in enumerate(ai_response.tasks, start=1)
        ]

        days = self._build_daily_days(ai_response=ai_response)
        print(f"🔥 GENERATED BASE DAYS COUNT: {len(days)}")

        try:
            days = await self.daily_task_detailing_service.enrich_days(
                context=context,
                days=days,
                response_language=response_language,
            )
            print(f"🔥 ENRICHED DAYS COUNT: {len(days)}")
        except Exception as e:
            print(f"⚠️ DAILY TASK DETAILING FAILED FOR PLAN: {e}")
            # Не валим весь flow. Оставляем базовые days.

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

    def _build_daily_days(self, ai_response: AIPlanResponseV2) -> list[dict]:
        total_days = max(7, ai_response.duration_weeks * 7)
        start_date = date.today()
        steps = ai_response.steps
        tasks = ai_response.tasks

        days: list[dict] = []

        for day_number in range(1, total_days + 1):
            planned_date = start_date + timedelta(days=day_number - 1)
            weekday = planned_date.isoweekday()
            step = self._pick_step_for_day(
                steps=steps,
                day_number=day_number,
                total_days=total_days,
            )

            day_tasks: list[dict] = []
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
                            "proof_prompt": None,
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
                first_task = tasks[0]
                day_tasks.append(
                    {
                        "title": first_task.title,
                        "description": first_task.description,
                        "objective": None,
                        "instructions": first_task.description,
                        "why_today": None,
                        "success_criteria": None,
                        "estimated_minutes": None,
                        "detail_level": 1,
                        "bucket": "must",
                        "priority": "medium",
                        "is_required": True,
                        "proof_required": first_task.proof_required,
                        "recommended_proof_type": first_task.proof_type,
                        "proof_prompt": None,
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
                    "main_task_title": None,
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
- If cadence_type is daily -> cadence_config must be {{}}
- If cadence_type is weekly -> cadence_config must include integer times_per_week
- If cadence_type is specific_weekdays -> cadence_config must include days_of_week with integers from 1 to 7
- Do not use phrases like:
  - try your best
  - stay motivated
  - believe in yourself
  - don't give up
  - think positively
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
      "proof_required": true
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