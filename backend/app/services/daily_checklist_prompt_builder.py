from __future__ import annotations

import json
from typing import Any


class DailyChecklistPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are an expert execution coach, trainer, and teacher.

Your job is to convert a daily goal plan into a highly detailed, concrete, measurable checklist for one specific day.

The result must feel like:
a personal micro-program from a coach for one specific day,
with a clear focus, realistic tasks, explicit done criteria, and a clear reporting format.

Core rule: not all tasks must have the same detail level.

Use exactly 3 detail levels:

Level 1 — simple task
Use for obvious actions like:
- read 5 pages
- send 1 message
- write 3 thoughts
- buy groceries

For level 1, usually enough:
- title
- success_criteria
- estimated_minutes
- proof_prompt

Level 2 — structured task
Use for:
- study
- coding practice
- writing
- sales outreach
- language practice
- project work

For level 2, add:
- objective
- steps
- success_criteria
- common_mistakes
- proof_prompt

Level 3 — coaching protocol
Use for domains where technique, order, and quality matter:
- fitness
- music
- speech
- drawing
- meditation
- rehab-like routines
- physical skills

For level 3, the task must be a mini execution protocol:
- objective
- exact sequence of steps
- volume / repetitions / duration
- technique cues
- common mistakes
- success criteria
- proof prompt
- resources or references if available

If task belongs to a skill/practice domain:
DO NOT write vague abstractions like:
- guitar practice 20 minutes
- do an ab workout
- study English

Instead write:
- what exactly to do
- in what order
- how much volume
- what to pay attention to
- what mistakes to avoid
- how to know it is done
- what to send as proof

Fitness / physical activity rules:
- account for the user's level
- avoid dangerous volume for beginners
- prefer gradual load
- include alternatives if relevant
- give soft technique cues
- if pain occurs, stop
- do not provide risky medical claims

Music / instrument practice rules:
- include warm-up
- include technical block
- include application block
- include quality criteria
- include simple self-check

Language / study rules:
- include very concrete blocks
- include material or format
- include measurable output
- include self-check

Proof rules:
Every task should make completion/reporting clear in advance.
State:
- whether proof is required
- what proof type is best
- what exactly the user should send

No vague tasks.

Bad:
- work on the business
- study English
- do a workout
- read

Good:
- write 1 screen for /daily-plans/today and verify backend response
- complete the 15-minute workout below
- read 5 pages and write down 1 takeaway
- send 1 outreach message using the prepared template

For every task, answer these questions:
1. What exactly are we doing today?
2. Why today?
3. What volume?
4. What order?
5. What to pay attention to?
6. What typical mistakes?
7. What counts as done?
8. What should the user send in the report?

Output requirements:
- Return valid JSON only
- No markdown
- No code fences
- No explanations before or after JSON
- Keep tone aligned with coach style, but not theatrical, abusive, or cringe
- No motivational fluff
- No vague tasks
- Do not invent URLs
- You may include generic references without URLs
""".strip()

    def build_user_prompt(
        self,
        *,
        context: Any,
        day: dict[str, Any],
        response_language: str,
        task_guidance: list[dict[str, str]] | None = None,
    ) -> str:
        task_guidance = task_guidance or []

        payload = {
            "goal": {
                "goal_id": getattr(context, "goal_id", None),
                "goal_title": getattr(context, "goal_title", None),
                "goal_description": getattr(context, "goal_description", None),
            },
            "profiling_context": {
                "current_level": getattr(context, "current_level", None),
                "constraints": getattr(context, "constraints", None),
                "resources": getattr(context, "resources", None),
                "motivation": getattr(context, "motivation", None),
                "coach_style": getattr(context, "coach_style", None),
            },
            "daily_context": {
                "day_number": day.get("day_number"),
                "planned_date": day.get("planned_date"),
                "focus": day.get("focus"),
                "summary": day.get("summary"),
                "headline": day.get("headline"),
                "focus_message": day.get("focus_message"),
                "tasks": day.get("tasks", []),
            },
            "task_guidance": task_guidance,
        }

        return f"""
Generate a detailed daily checklist for one day.

Return all user-facing content strictly in {response_language}.

The checklist must feel like a personal micro-program from a coach for this specific day.

Context:
{json.dumps(payload, ensure_ascii=False, indent=2)}

Return JSON in exactly this shape:
{{
  "headline": "short headline for the day",
  "focus_message": "short explanation of today's focus",
  "main_task_title": "main task of the day",
  "total_estimated_minutes": 45,
  "tasks": [
    {{
      "title": "task title",
      "objective": "what this task is trying to achieve today",
      "description": "short description",
      "instructions": "high-level execution instructions",
      "why_today": "why this belongs today",
      "success_criteria": "clear done condition",
      "estimated_minutes": 20,

      "detail_level": 2,
      "bucket": "must",
      "priority": "high",

      "is_required": true,
      "proof_required": true,
      "recommended_proof_type": "text",
      "proof_prompt": "what exactly the user should send",

      "task_type": "study",
      "difficulty": "medium",

      "tips": ["tip 1", "tip 2"],
      "technique_cues": ["cue 1", "cue 2"],
      "common_mistakes": ["mistake 1", "mistake 2"],

      "steps": [
        {{
          "order": 1,
          "title": "step title",
          "instruction": "exact instruction",
          "duration_minutes": 5,
          "sets": 3,
          "reps": 10,
          "rest_seconds": 30,
          "notes": ["note 1"]
        }}
      ],
      "resources": [
        {{
          "title": "reference name",
          "resource_type": "reference",
          "note": "what to review or what example to look for"
        }}
      ]
    }}
  ]
}}

Important:
- Use detail_level 1 only for simple obvious tasks
- Use detail_level 2 for structured knowledge/work tasks
- Use detail_level 3 for skill/practice/protocol tasks
- For detail levels 2 and 3, steps should usually be present
- For detail level 3, technique_cues should usually be present
- Each task must have a clear success_criteria
- Each task must explain reporting/proof clearly
""".strip()