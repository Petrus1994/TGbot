from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.config import settings
from app.schemas.ai_daily_checklist import AIDailyChecklistResponse
from app.services.daily_checklist_prompt_builder import DailyChecklistPromptBuilder
from app.services.daily_task_template_service import DailyTaskTemplateService
from app.services.openai_client import OpenAIClient


class DailyTaskDetailingService:
    def __init__(self) -> None:
        self.prompt_builder = DailyChecklistPromptBuilder()
        self.template_service = DailyTaskTemplateService()
        self.llm_client = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def enrich_days(
        self,
        *,
        context: Any,
        days: list[dict[str, Any]],
        response_language: str,
    ) -> list[dict[str, Any]]:
        enriched_days: list[dict[str, Any]] = []

        for day in days:
            enriched_day = await self.enrich_single_day(
                context=context,
                day=day,
                response_language=response_language,
            )
            enriched_days.append(enriched_day)

        return enriched_days

    async def enrich_single_day(
        self,
        *,
        context: Any,
        day: dict[str, Any],
        response_language: str,
    ) -> dict[str, Any]:
        raw_tasks = day.get("tasks", [])
        task_guidance = self._build_task_guidance(raw_tasks)

        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(
            context=context,
            day=day,
            response_language=response_language,
            task_guidance=task_guidance,
        )

        try:
            raw_response = await self.llm_client.generate_plan(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            normalized_response = self._normalize_ai_daily_checklist_payload(raw_response)
            parsed = AIDailyChecklistResponse.model_validate(normalized_response)
            self._validate_ai_daily_checklist(
                ai_response=parsed,
                raw_tasks_count=len(raw_tasks),
            )
            return self._merge_day_with_ai_response(
                day=day,
                ai_response=parsed,
            )
        except Exception as e:
            print(
                f"⚠️ DAILY CHECKLIST ENRICH FAILED: "
                f"day={day.get('day_number')} error={e}"
            )
            return self._fallback_enrich_day(day=day)

    def _build_task_guidance(self, tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
        guidance: list[dict[str, str]] = []

        for task in tasks:
            title = str(task.get("title") or "")
            description = str(task.get("description") or "")
            task_type = self.template_service.infer_task_type(
                title=title,
                description=description,
            )
            rule = self.template_service.build_task_guidance(task_type)

            guidance.append(
                {
                    "title": title,
                    "inferred_task_type": task_type,
                    "guidance": rule,
                }
            )

        return guidance

    def _validate_ai_daily_checklist(
        self,
        *,
        ai_response: AIDailyChecklistResponse,
        raw_tasks_count: int,
    ) -> None:
        if not ai_response.headline.strip():
            raise ValueError("daily checklist headline is empty")

        if raw_tasks_count > 0 and len(ai_response.tasks) == 0:
            raise ValueError("daily checklist returned zero tasks")

        if ai_response.total_estimated_minutes is not None and ai_response.total_estimated_minutes < 1:
            raise ValueError("total_estimated_minutes must be >= 1")

        forbidden_phrases = [
            "постарайся",
            "не сдавайся",
            "верь в себя",
            "stay motivated",
            "believe in yourself",
            "try your best",
            "don't give up",
        ]

        allowed_buckets = {"must", "should", "bonus"}
        allowed_priorities = {"high", "medium", "low"}

        for task in ai_response.tasks:
            blob = " ".join(
                [
                    task.title or "",
                    task.description or "",
                    task.objective or "",
                    task.instructions or "",
                    task.why_today or "",
                    task.success_criteria or "",
                    " ".join(task.tips),
                    " ".join(task.technique_cues),
                    " ".join(task.common_mistakes),
                ]
            ).lower()

            for phrase in forbidden_phrases:
                if phrase in blob:
                    raise ValueError(f"forbidden phrase in daily checklist: {phrase}")

            if not task.title.strip():
                raise ValueError("task title is empty")

            if task.estimated_minutes is not None and task.estimated_minutes < 1:
                raise ValueError("estimated_minutes must be >= 1")

            if task.bucket not in allowed_buckets:
                raise ValueError(f"invalid task bucket: {task.bucket}")

            if task.priority not in allowed_priorities:
                raise ValueError(f"invalid task priority: {task.priority}")

            if task.detail_level not in {1, 2, 3}:
                raise ValueError(f"invalid detail_level: {task.detail_level}")

            if not task.success_criteria or not task.success_criteria.strip():
                raise ValueError("task success_criteria is required")

            if not task.why_today or not task.why_today.strip():
                raise ValueError("task why_today is required")

            if task.proof_required:
                if not task.recommended_proof_type:
                    raise ValueError("proof_required task must have recommended_proof_type")
                if not task.proof_prompt or not task.proof_prompt.strip():
                    raise ValueError("proof_required task must have proof_prompt")

            if task.detail_level == 1:
                if task.task_type in {"fitness", "music", "speech", "drawing", "meditation", "rehab"}:
                    raise ValueError(
                        f"{task.task_type} task cannot use detail_level 1"
                    )

            if task.detail_level == 2:
                if not task.steps:
                    raise ValueError("detail_level 2 task must contain steps")

            if task.detail_level == 3:
                if not task.steps:
                    raise ValueError("detail_level 3 task must contain steps")
                if task.task_type in {
                    "fitness",
                    "music",
                    "speech",
                    "drawing",
                    "meditation",
                    "rehab",
                } and not task.technique_cues:
                    raise ValueError(
                        f"{task.task_type} detail_level 3 task should contain technique_cues"
                    )

            if task.task_type in {"fitness", "music", "language", "study"} and not task.steps:
                raise ValueError(f"{task.task_type} task must contain steps")

        if ai_response.tasks:
            calculated_total = sum(
                task.estimated_minutes or 0 for task in ai_response.tasks
            )
            if (
                ai_response.total_estimated_minutes is not None
                and calculated_total > 0
                and abs(ai_response.total_estimated_minutes - calculated_total) > 20
            ):
                raise ValueError(
                    "total_estimated_minutes differs too much from sum of task durations"
                )

    def _merge_day_with_ai_response(
        self,
        *,
        day: dict[str, Any],
        ai_response: AIDailyChecklistResponse,
    ) -> dict[str, Any]:
        merged = deepcopy(day)
        merged["headline"] = ai_response.headline
        merged["focus_message"] = ai_response.focus_message
        merged["main_task_title"] = ai_response.main_task_title
        merged["total_estimated_minutes"] = ai_response.total_estimated_minutes
        merged["tasks"] = [
            self._map_ai_task_to_generated_task(task)
            for task in ai_response.tasks
        ]
        return merged

    def _map_ai_task_to_generated_task(self, task) -> dict[str, Any]:
        return {
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
            "steps": [
                {
                    "order": step.order,
                    "title": step.title,
                    "instruction": step.instruction,
                    "duration_minutes": step.duration_minutes,
                    "sets": step.sets,
                    "reps": step.reps,
                    "rest_seconds": step.rest_seconds,
                    "notes": step.notes,
                }
                for step in task.steps
            ],
            "resources": [
                {
                    "title": resource.title,
                    "resource_type": resource.resource_type,
                    "note": resource.note,
                }
                for resource in task.resources
            ],
        }

    def _fallback_enrich_day(self, *, day: dict[str, Any]) -> dict[str, Any]:
        fallback_day = deepcopy(day)

        fallback_day["headline"] = (
            fallback_day.get("headline")
            or fallback_day.get("focus")
            or "Plan for today"
        )
        fallback_day["focus_message"] = (
            fallback_day.get("focus_message")
            or fallback_day.get("summary")
        )

        enriched_tasks: list[dict[str, Any]] = []

        for index, task in enumerate(fallback_day.get("tasks", []), start=1):
            title = str(task.get("title") or f"Task {index}")
            description = task.get("description")
            instructions = task.get("instructions") or description or f"Complete the task: {title}"
            estimated_minutes = task.get("estimated_minutes") or 20
            proof_required = bool(task.get("proof_required", False))
            is_required = bool(task.get("is_required", True))

            task_type = self.template_service.infer_task_type(
                title=title,
                description=str(description or ""),
            )

            detail_level = self._infer_fallback_detail_level(task_type=task_type)
            bucket = "must" if is_required else "should"
            priority = "high" if is_required else "medium"
            why_today = (
                fallback_day.get("focus_message")
                or fallback_day.get("summary")
                or f"This task supports today's focus: {fallback_day.get('focus') or 'execution'}."
            )

            technique_cues = self._fallback_technique_cues(task_type=task_type)
            steps = self._fallback_steps(
                title=title,
                instructions=instructions,
                estimated_minutes=estimated_minutes,
                task_type=task_type,
                detail_level=detail_level,
            )

            enriched_tasks.append(
                {
                    "title": title,
                    "objective": description or f"Complete: {title}",
                    "description": description,
                    "instructions": instructions,
                    "why_today": why_today,
                    "success_criteria": f"Task completed: {title}",
                    "estimated_minutes": estimated_minutes,
                    "detail_level": detail_level,
                    "bucket": bucket,
                    "priority": priority,
                    "is_required": is_required,
                    "proof_required": proof_required,
                    "recommended_proof_type": "text" if proof_required else None,
                    "proof_prompt": (
                        "Send a short text report about what you completed."
                        if proof_required
                        else None
                    ),
                    "task_type": task_type,
                    "difficulty": "medium",
                    "tips": [],
                    "technique_cues": technique_cues,
                    "common_mistakes": [],
                    "steps": steps,
                    "resources": [],
                }
            )

        fallback_day["tasks"] = enriched_tasks
        fallback_day["main_task_title"] = self._pick_main_task_title(enriched_tasks)
        fallback_day["total_estimated_minutes"] = sum(
            task.get("estimated_minutes") or 0 for task in enriched_tasks
        )

        return fallback_day

    def _infer_fallback_detail_level(self, *, task_type: str) -> int:
        if task_type in {"fitness", "music", "speech", "drawing", "meditation", "rehab"}:
            return 3
        if task_type in {"language", "study", "work"}:
            return 2
        return 1

    def _fallback_technique_cues(self, *, task_type: str) -> list[str]:
        mapping = {
            "fitness": [
                "Move with control, not with momentum.",
                "Stop if you feel pain.",
            ],
            "music": [
                "Prioritize clean execution over speed.",
                "Reduce tempo if quality drops.",
            ],
            "speech": [
                "Focus on clarity before speed.",
                "Keep breathing steady and controlled.",
            ],
            "drawing": [
                "Focus on accuracy before adding detail.",
                "Keep the hand relaxed and controlled.",
            ],
            "meditation": [
                "Return attention gently when distracted.",
                "Do not force the process.",
            ],
            "rehab": [
                "Move carefully and without sharp pain.",
                "Use conservative effort and controlled range.",
            ],
        }
        return mapping.get(task_type, [])

    def _fallback_steps(
        self,
        *,
        title: str,
        instructions: str,
        estimated_minutes: int,
        task_type: str,
        detail_level: int,
    ) -> list[dict[str, Any]]:
        if detail_level == 1:
            return []

        if detail_level == 2:
            first_block = max(5, estimated_minutes // 2)
            second_block = max(5, estimated_minutes - first_block)

            return [
                {
                    "order": 1,
                    "title": "Start the task",
                    "instruction": instructions,
                    "duration_minutes": first_block,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": [],
                },
                {
                    "order": 2,
                    "title": "Finish and verify",
                    "instruction": f"Complete the task and verify the result for: {title}",
                    "duration_minutes": second_block,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": [],
                },
            ]

        if task_type == "fitness":
            warmup_minutes = min(5, estimated_minutes)
            main_minutes = max(5, estimated_minutes - warmup_minutes)

            return [
                {
                    "order": 1,
                    "title": "Warm-up",
                    "instruction": "Do a short easy warm-up and prepare for the main work.",
                    "duration_minutes": warmup_minutes,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": ["Keep intensity low at the start."],
                },
                {
                    "order": 2,
                    "title": "Main block",
                    "instruction": instructions,
                    "duration_minutes": main_minutes,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": 30,
                    "notes": ["Use controlled technique.", "Stop if pain appears."],
                },
            ]

        if task_type == "music":
            warmup_minutes = min(5, estimated_minutes)
            technical_minutes = max(5, estimated_minutes // 2)
            application_minutes = max(5, estimated_minutes - warmup_minutes - technical_minutes)

            return [
                {
                    "order": 1,
                    "title": "Warm-up",
                    "instruction": "Start with an easy warm-up to prepare hands and coordination.",
                    "duration_minutes": warmup_minutes,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": ["Stay slow and clean."],
                },
                {
                    "order": 2,
                    "title": "Technical block",
                    "instruction": instructions,
                    "duration_minutes": technical_minutes,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": ["Prioritize clean execution over speed."],
                },
                {
                    "order": 3,
                    "title": "Application block",
                    "instruction": "Apply the practiced skill in a short controlled run-through.",
                    "duration_minutes": application_minutes,
                    "sets": None,
                    "reps": None,
                    "rest_seconds": None,
                    "notes": ["Do at least one clean full attempt."],
                },
            ]

        setup_minutes = min(5, estimated_minutes)
        main_minutes = max(5, estimated_minutes - setup_minutes)

        return [
            {
                "order": 1,
                "title": "Setup",
                "instruction": "Prepare for the practice session.",
                "duration_minutes": setup_minutes,
                "sets": None,
                "reps": None,
                "rest_seconds": None,
                "notes": [],
            },
            {
                "order": 2,
                "title": "Main practice",
                "instruction": instructions,
                "duration_minutes": main_minutes,
                "sets": None,
                "reps": None,
                "rest_seconds": None,
                "notes": [],
            },
        ]

    def _pick_main_task_title(self, tasks: list[dict[str, Any]]) -> str | None:
        if not tasks:
            return None

        high_priority_must_tasks = [
            task for task in tasks
            if task.get("bucket") == "must" and task.get("priority") == "high"
        ]
        if high_priority_must_tasks:
            return str(high_priority_must_tasks[0].get("title"))

        must_tasks = [task for task in tasks if task.get("bucket") == "must"]
        if must_tasks:
            return str(must_tasks[0].get("title"))

        return str(tasks[0].get("title"))

    def _normalize_ai_daily_checklist_payload(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return payload

        normalized = deepcopy(payload)

        tasks = normalized.get("tasks")
        if not isinstance(tasks, list):
            return normalized

        normalized_tasks: list[dict[str, Any]] = []

        for task in tasks:
            if not isinstance(task, dict):
                continue
            normalized_tasks.append(self._normalize_ai_task_payload(task))

        normalized["tasks"] = normalized_tasks
        return normalized

    def _normalize_ai_task_payload(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = deepcopy(task)

        normalized["task_type"] = self._normalize_task_type(
            normalized.get("task_type")
        )
        normalized["bucket"] = self._normalize_bucket(
            normalized.get("bucket")
        )
        normalized["priority"] = self._normalize_priority(
            normalized.get("priority")
        )
        normalized["difficulty"] = self._normalize_difficulty(
            normalized.get("difficulty")
        )
        normalized["recommended_proof_type"] = self._normalize_proof_type(
            normalized.get("recommended_proof_type")
        )

        detail_level = normalized.get("detail_level")
        try:
            normalized["detail_level"] = int(detail_level)
        except Exception:
            normalized["detail_level"] = self._default_detail_level_for_task_type(
                normalized["task_type"]
            )

        resources = normalized.get("resources")
        if isinstance(resources, list):
            fixed_resources: list[dict[str, Any]] = []
            for resource in resources:
                if not isinstance(resource, dict):
                    continue
                resource_copy = deepcopy(resource)
                resource_copy["resource_type"] = self._normalize_resource_type(
                    resource_copy.get("resource_type")
                )
                fixed_resources.append(resource_copy)
            normalized["resources"] = fixed_resources

        steps = normalized.get("steps")
        if isinstance(steps, list):
            fixed_steps: list[dict[str, Any]] = []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                step_copy = deepcopy(step)

                if step_copy.get("rest_seconds") is not None:
                    try:
                        step_copy["rest_seconds"] = max(0, int(step_copy["rest_seconds"]))
                    except Exception:
                        step_copy["rest_seconds"] = None

                for field_name in ("order", "duration_minutes", "sets", "reps"):
                    if step_copy.get(field_name) is not None:
                        try:
                            step_copy[field_name] = int(step_copy[field_name])
                        except Exception:
                            step_copy[field_name] = None

                fixed_steps.append(step_copy)
            normalized["steps"] = fixed_steps

        return normalized

    def _normalize_task_type(self, value: Any) -> str:
        allowed = {
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

        if value is None:
            return "generic"

        text = str(value).strip().lower()

        mapping = {
            "planning": "work",
            "tracking": "habit",
            "exercise": "fitness",
            "workout": "fitness",
            "instrument": "music",
            "practice": "study",
            "learning": "study",
            "productivity": "work",
            "organization": "work",
            "health": "habit",
            "wellness": "habit",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else "generic"

    def _normalize_bucket(self, value: Any) -> str:
        allowed = {"must", "should", "bonus"}

        if value is None:
            return "must"

        text = str(value).strip().lower()
        mapping = {
            "required": "must",
            "core": "must",
            "important": "must",
            "optional": "bonus",
            "extra": "bonus",
            "nice_to_have": "should",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else "must"

    def _normalize_priority(self, value: Any) -> str:
        allowed = {"high", "medium", "low"}

        if value is None:
            return "medium"

        text = str(value).strip().lower()
        mapping = {
            "urgent": "high",
            "critical": "high",
            "normal": "medium",
            "standard": "medium",
            "optional": "low",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else "medium"

    def _normalize_difficulty(self, value: Any) -> str | None:
        allowed = {"easy", "medium", "hard"}

        if value is None:
            return None

        text = str(value).strip().lower()
        mapping = {
            "beginner": "easy",
            "light": "easy",
            "moderate": "medium",
            "intermediate": "medium",
            "advanced": "hard",
            "difficult": "hard",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else None

    def _normalize_proof_type(self, value: Any) -> str | None:
        allowed = {"text", "photo", "screenshot", "file", "video"}

        if value is None:
            return None

        text = str(value).strip().lower()
        mapping = {
            "image": "photo",
            "picture": "photo",
            "screen": "screenshot",
            "doc": "file",
            "document": "file",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else None

    def _normalize_resource_type(self, value: Any) -> str:
        allowed = {"video", "article", "reference", "checklist", "tool"}

        if value is None:
            return "reference"

        text = str(value).strip().lower()
        mapping = {
            "app": "tool",
            "template": "checklist",
            "guide": "reference",
            "tutorial": "video",
        }

        normalized = mapping.get(text, text)
        return normalized if normalized in allowed else "reference"

    def _default_detail_level_for_task_type(self, task_type: str) -> int:
        if task_type in {"fitness", "music", "speech", "drawing", "meditation", "rehab"}:
            return 3
        if task_type in {"language", "study", "work", "nutrition", "activity"}:
            return 2
        return 1