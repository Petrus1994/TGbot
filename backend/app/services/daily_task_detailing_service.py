from __future__ import annotations

from typing import Any

from app.config import settings
from app.core.exceptions import AIPlanGenerationError, AIResponseValidationError
from app.schemas.ai_daily_checklist import AIDailyChecklistResponse
from app.schemas.goal_generation import GoalGenerationContext
from app.services.daily_checklist_prompt_builder import DailyChecklistPromptBuilder
from app.services.openai_client import OpenAIClient


class DailyTaskDetailingService:
    ALLOWED_BUCKETS = {"must", "should", "bonus"}
    ALLOWED_PRIORITIES = {"high", "medium", "low"}
    ALLOWED_DIFFICULTIES = {"easy", "medium", "hard"}
    ALLOWED_TASK_TYPES = {
        "fitness",
        "music",
        "language",
        "study",
        "work",
        "habit",
        "speech",
        "drawing",
        "meditation",
        "rehab",
        "nutrition",
        "activity",
        "generic",
    }
    ALLOWED_PROOF_TYPES = {"text", "photo", "screenshot", "file", "video"}
    ALLOWED_RESOURCE_TYPES = {"video", "article", "reference", "checklist", "tool"}

    def __init__(self) -> None:
        self.prompt_builder = DailyChecklistPromptBuilder()
        self.llm_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def enrich_single_day(
        self,
        *,
        context: GoalGenerationContext,
        day: dict[str, Any],
        response_language: str,
    ) -> dict[str, Any]:
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(
            context=context,
            day=day,
            response_language=response_language,
        )

        ai_response = await self._generate_with_retry(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_language=response_language,
            original_day=day,
        )

        return self._map_response_to_day_payload(
            original_day=day,
            ai_response=ai_response,
        )

    async def _generate_with_retry(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_language: str,
        original_day: dict[str, Any],
    ) -> AIDailyChecklistResponse:
        first_error: Exception | None = None

        try:
            raw_response = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            parsed = self._parse_and_validate_ai_response(
                raw_response=raw_response,
                original_day=original_day,
            )
            return parsed
        except Exception as e:
            first_error = e

        retry_user_prompt = self._build_retry_user_prompt(
            original_user_prompt=user_prompt,
            response_language=response_language,
            original_day=original_day,
        )

        try:
            raw_response = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=retry_user_prompt,
            )
            parsed = self._parse_and_validate_ai_response(
                raw_response=raw_response,
                original_day=original_day,
            )
            return parsed
        except Exception as retry_error:
            raise AIPlanGenerationError(
                f"daily_detailing_failed_after_retry | first_error={first_error} | retry_error={retry_error}"
            ) from retry_error

    def _parse_and_validate_ai_response(
        self,
        *,
        raw_response: Any,
        original_day: dict[str, Any],
    ) -> AIDailyChecklistResponse:
        normalized_payload = self._normalize_ai_response_payload(
            raw_response=raw_response,
            original_day=original_day,
        )
        ai_response = AIDailyChecklistResponse.model_validate(normalized_payload)
        self._validate_ai_response(ai_response, original_day=original_day)
        return ai_response

    def _normalize_ai_response_payload(
        self,
        *,
        raw_response: Any,
        original_day: dict[str, Any],
    ) -> dict[str, Any]:
        if hasattr(raw_response, "model_dump"):
            payload = raw_response.model_dump()
        elif isinstance(raw_response, dict):
            payload = dict(raw_response)
        else:
            raise AIResponseValidationError("daily_ai_response_not_a_dict")

        payload["headline"] = self._safe_text(payload.get("headline")) or self._safe_text(
            original_day.get("focus")
        ) or "Execution plan"
        payload["focus_message"] = self._safe_text(payload.get("focus_message"))
        payload["main_task_title"] = self._safe_text(payload.get("main_task_title"))
        payload["total_estimated_minutes"] = self._normalize_positive_int_or_none(
            payload.get("total_estimated_minutes")
        )

        payload["tasks"] = self._normalize_tasks(
            raw_tasks=payload.get("tasks"),
            original_day=original_day,
        )

        if payload["total_estimated_minutes"] is None:
            computed_total = sum(
                task.get("estimated_minutes") or 0 for task in payload["tasks"]
            )
            payload["total_estimated_minutes"] = computed_total or None

        return payload

    def _normalize_tasks(
        self,
        *,
        raw_tasks: Any,
        original_day: dict[str, Any],
    ) -> list[dict[str, Any]]:
        original_tasks = original_day.get("tasks", [])
        source_tasks = raw_tasks if isinstance(raw_tasks, list) else []

        normalized_tasks: list[dict[str, Any]] = []

        if not source_tasks and isinstance(original_tasks, list):
            source_tasks = original_tasks

        for index, item in enumerate(source_tasks, start=1):
            if not isinstance(item, dict):
                continue

            original_task = (
                original_tasks[index - 1]
                if isinstance(original_tasks, list) and len(original_tasks) >= index
                else {}
            )
            if not isinstance(original_task, dict):
                original_task = {}

            title = self._safe_text(item.get("title")) or self._safe_text(
                original_task.get("title")
            ) or f"Task {index}"

            description = self._safe_text(item.get("description")) or self._safe_text(
                original_task.get("description")
            ) or self._safe_text(item.get("instructions")) or "Complete the assigned task."

            instructions = self._safe_text(item.get("instructions")) or self._safe_text(
                original_task.get("instructions")
            ) or description

            objective = self._safe_text(item.get("objective")) or self._safe_text(
                original_task.get("objective")
            )
            why_today = self._safe_text(item.get("why_today")) or self._safe_text(
                original_task.get("why_today")
            )
            success_criteria = self._safe_text(
                item.get("success_criteria")
            ) or self._safe_text(original_task.get("success_criteria"))

            estimated_minutes = self._normalize_positive_int_or_none(
                item.get("estimated_minutes")
            )
            if estimated_minutes is None:
                estimated_minutes = self._normalize_positive_int_or_none(
                    original_task.get("estimated_minutes")
                )

            detail_level = self._normalize_detail_level(item.get("detail_level"))
            bucket = self._normalize_bucket(item.get("bucket"))
            priority = self._normalize_priority(item.get("priority"))

            is_required = self._normalize_bool(
                item.get("is_required"),
                default=bool(original_task.get("is_required", True)),
            )
            proof_required = self._normalize_bool(
                item.get("proof_required"),
                default=bool(original_task.get("proof_required", False)),
            )

            recommended_proof_type = self._normalize_proof_type(
                item.get("recommended_proof_type")
            )
            if recommended_proof_type is None:
                recommended_proof_type = self._normalize_proof_type(
                    original_task.get("recommended_proof_type")
                )

            proof_prompt = self._safe_text(item.get("proof_prompt")) or self._safe_text(
                original_task.get("proof_prompt")
            )

            task_type = self._normalize_task_type(item.get("task_type"))
            if task_type == "generic":
                task_type = self._normalize_task_type(original_task.get("task_type"))

            difficulty = self._normalize_difficulty(item.get("difficulty"))
            if difficulty is None:
                difficulty = self._normalize_difficulty(original_task.get("difficulty"))

            tips = self._normalize_string_list(item.get("tips"))
            technique_cues = self._normalize_string_list(item.get("technique_cues"))
            common_mistakes = self._normalize_string_list(item.get("common_mistakes"))

            steps = self._normalize_steps(item.get("steps"))
            resources = self._normalize_resources(item.get("resources"))

            normalized_tasks.append(
                {
                    "title": title,
                    "objective": objective,
                    "description": description,
                    "instructions": instructions,
                    "why_today": why_today,
                    "success_criteria": success_criteria,
                    "estimated_minutes": estimated_minutes,
                    "detail_level": detail_level,
                    "bucket": bucket,
                    "priority": priority,
                    "is_required": is_required,
                    "proof_required": proof_required,
                    "recommended_proof_type": recommended_proof_type,
                    "proof_prompt": proof_prompt,
                    "task_type": task_type,
                    "difficulty": difficulty,
                    "tips": tips,
                    "technique_cues": technique_cues,
                    "common_mistakes": common_mistakes,
                    "steps": steps,
                    "resources": resources,
                }
            )

        return normalized_tasks

    def _normalize_steps(self, raw_steps: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_steps, list):
            return []

        normalized_steps: list[dict[str, Any]] = []

        for index, item in enumerate(raw_steps, start=1):
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title")) or f"Step {index}"
            instruction = self._safe_text(item.get("instruction"))
            if not instruction:
                continue

            normalized_steps.append(
                {
                    "order": self._normalize_positive_int(item.get("order"), default=index),
                    "title": title,
                    "instruction": instruction,
                    "duration_minutes": self._normalize_positive_int_or_none(
                        item.get("duration_minutes")
                    ),
                    "sets": self._normalize_positive_int_or_none(item.get("sets")),
                    "reps": self._normalize_positive_int_or_none(item.get("reps")),
                    "rest_seconds": self._normalize_non_negative_int_or_none(
                        item.get("rest_seconds")
                    ),
                    "notes": self._normalize_string_list(item.get("notes")),
                }
            )

        return normalized_steps

    def _normalize_resources(self, raw_resources: Any) -> list[dict[str, Any]]:
        if not isinstance(raw_resources, list):
            return []

        normalized_resources: list[dict[str, Any]] = []

        for item in raw_resources:
            if not isinstance(item, dict):
                continue

            title = self._safe_text(item.get("title"))
            resource_type = self._normalize_resource_type(item.get("resource_type"))
            note = self._safe_text(item.get("note"))

            if not title or not resource_type:
                continue

            normalized_resources.append(
                {
                    "title": title,
                    "resource_type": resource_type,
                    "note": note,
                }
            )

        return normalized_resources

    def _validate_ai_response(
        self,
        ai_response: AIDailyChecklistResponse,
        *,
        original_day: dict[str, Any],
    ) -> None:
        if not ai_response.headline.strip():
            raise AIResponseValidationError("daily_ai_headline_empty")

        tasks = ai_response.tasks
        original_tasks = original_day.get("tasks", [])
        min_required = 1 if not isinstance(original_tasks, list) else max(1, len(original_tasks))

        if len(tasks) < min_required:
            raise AIResponseValidationError("daily_ai_not_enough_tasks")

        forbidden_phrases = [
            "stay focused",
            "stay disciplined",
            "give your best",
            "stay consistent",
            "постарайся",
            "не сдавайся",
            "будь дисциплинирован",
            "просто сделай это",
        ]

        for task in tasks:
            if not task.title.strip():
                raise AIResponseValidationError("daily_ai_task_title_empty")

            text_to_check = " ".join(
                part
                for part in [
                    task.title,
                    task.description or "",
                    task.instructions or "",
                    task.why_today or "",
                    task.success_criteria or "",
                ]
                if part
            ).lower()

            for phrase in forbidden_phrases:
                if phrase in text_to_check:
                    raise AIResponseValidationError(
                        f"daily_ai_contains_forbidden_phrase: {phrase}"
                    )

            if task.is_required:
                if not task.instructions:
                    raise AIResponseValidationError("daily_ai_required_task_missing_instructions")
                if not task.success_criteria:
                    raise AIResponseValidationError(
                        "daily_ai_required_task_missing_success_criteria"
                    )
                if not task.why_today:
                    raise AIResponseValidationError("daily_ai_required_task_missing_why_today")

            if task.detail_level >= 2 and not task.steps:
                practical_types = {
                    "fitness",
                    "music",
                    "language",
                    "study",
                    "work",
                    "speech",
                    "drawing",
                    "rehab",
                    "nutrition",
                    "activity",
                }
                if task.task_type in practical_types:
                    raise AIResponseValidationError(
                        "daily_ai_detailed_practical_task_missing_steps"
                    )

    def _map_response_to_day_payload(
        self,
        *,
        original_day: dict[str, Any],
        ai_response: AIDailyChecklistResponse,
    ) -> dict[str, Any]:
        original_day_number = original_day.get("day_number")
        original_planned_date = original_day.get("planned_date")
        original_focus = original_day.get("focus")
        original_summary = original_day.get("summary")

        return {
            "day_number": original_day_number,
            "planned_date": original_planned_date,
            "focus": original_focus,
            "summary": original_summary,
            "headline": ai_response.headline,
            "focus_message": ai_response.focus_message,
            "main_task_title": ai_response.main_task_title,
            "total_estimated_minutes": ai_response.total_estimated_minutes,
            "tasks": [
                {
                    "title": task.title,
                    "objective": task.objective,
                    "description": task.description,
                    "instructions": task.instructions,
                    "why_today": task.why_today,
                    "success_criteria": task.success_criteria,
                    "estimated_minutes": task.estimated_minutes,
                    "detail_level": task.detail_level,
                    "bucket": task.bucket,
                    "priority": task.priority,
                    "is_required": task.is_required,
                    "proof_required": task.proof_required,
                    "recommended_proof_type": task.recommended_proof_type,
                    "proof_prompt": task.proof_prompt,
                    "task_type": task.task_type,
                    "difficulty": task.difficulty,
                    "tips": task.tips,
                    "technique_cues": task.technique_cues,
                    "common_mistakes": task.common_mistakes,
                    "steps": [step.model_dump() for step in task.steps],
                    "resources": [resource.model_dump() for resource in task.resources],
                }
                for task in ai_response.tasks
            ],
        }

    def _build_retry_user_prompt(
        self,
        *,
        original_user_prompt: str,
        response_language: str,
        original_day: dict[str, Any],
    ) -> str:
        original_task_count = len(original_day.get("tasks", [])) if isinstance(
            original_day.get("tasks"), list
        ) else 1

        return f"""
The previous answer was invalid.

Fix it now.

STRICT REQUIREMENTS:
- Return valid JSON only
- No markdown
- No code fences
- No explanations
- All user-facing content must be strictly in {response_language}
- Do not mix languages
- Keep the same day scope
- Return at least {max(1, original_task_count)} tasks
- Headline must be non-empty
- Every required task must include:
  - instructions
  - why_today
  - success_criteria
- For practical or skill-based tasks with detail_level >= 2, include step-by-step steps
- Do not use motivational fluff
- Do not use phrases like:
  - stay focused
  - stay disciplined
  - give your best
  - stay consistent
  - постарайся
  - не сдавайся
  - будь дисциплинирован

VALID ENUMS:
- bucket: must, should, bonus
- priority: high, medium, low
- difficulty: easy, medium, hard
- task_type:
  fitness, music, language, study, work, habit, speech, drawing, meditation, rehab, nutrition, activity, generic
- recommended_proof_type:
  text, photo, screenshot, file, video
- resource_type:
  video, article, reference, checklist, tool

RETURN JSON IN THIS SHAPE:
{{
  "headline": "string",
  "focus_message": "string or null",
  "main_task_title": "string or null",
  "total_estimated_minutes": 90,
  "tasks": [
    {{
      "title": "string",
      "objective": "string or null",
      "description": "string or null",
      "instructions": "string or null",
      "why_today": "string or null",
      "success_criteria": "string or null",
      "estimated_minutes": 30,
      "detail_level": 2,
      "bucket": "must",
      "priority": "high",
      "is_required": true,
      "proof_required": true,
      "recommended_proof_type": "text",
      "proof_prompt": "string or null",
      "task_type": "generic",
      "difficulty": "medium",
      "tips": [],
      "technique_cues": [],
      "common_mistakes": [],
      "steps": [],
      "resources": []
    }}
  ]
}}

Original task:
{original_user_prompt}
""".strip()

    def _normalize_bucket(self, value: Any) -> str:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_BUCKETS else "must"

    def _normalize_priority(self, value: Any) -> str:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_PRIORITIES else "medium"

    def _normalize_difficulty(self, value: Any) -> str | None:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_DIFFICULTIES else None

    def _normalize_task_type(self, value: Any) -> str:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_TASK_TYPES else "generic"

    def _normalize_proof_type(self, value: Any) -> str | None:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_PROOF_TYPES else None

    def _normalize_resource_type(self, value: Any) -> str | None:
        normalized = (self._safe_text(value) or "").lower()
        return normalized if normalized in self.ALLOWED_RESOURCE_TYPES else None

    def _normalize_detail_level(self, value: Any) -> int:
        parsed = self._normalize_positive_int(value, default=2)
        if parsed < 1:
            return 1
        if parsed > 3:
            return 3
        return parsed

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

        text_value = self._safe_text(value)
        return [text_value] if text_value else []

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

    def _normalize_positive_int(self, raw_value: Any, default: int) -> int:
        if raw_value is None:
            return default

        if isinstance(raw_value, bool):
            return default

        if isinstance(raw_value, int):
            return raw_value if raw_value > 0 else default

        try:
            parsed = int(str(raw_value).strip())
            return parsed if parsed > 0 else default
        except Exception:
            return default

    def _normalize_positive_int_or_none(self, raw_value: Any) -> int | None:
        if raw_value is None or raw_value == "":
            return None

        if isinstance(raw_value, bool):
            return None

        if isinstance(raw_value, int):
            return raw_value if raw_value > 0 else None

        try:
            parsed = int(str(raw_value).strip())
            return parsed if parsed > 0 else None
        except Exception:
            return None

    def _normalize_non_negative_int_or_none(self, raw_value: Any) -> int | None:
        if raw_value is None or raw_value == "":
            return None

        if isinstance(raw_value, bool):
            return None

        if isinstance(raw_value, int):
            return raw_value if raw_value >= 0 else None

        try:
            parsed = int(str(raw_value).strip())
            return parsed if parsed >= 0 else None
        except Exception:
            return None

    def _safe_text(self, value: Any) -> str | None:
        if value is None:
            return None

        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None

        normalized = str(value).strip()
        return normalized or None