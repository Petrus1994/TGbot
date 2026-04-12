from __future__ import annotations

import json

from app.schemas.goal_generation import GoalGenerationContext


class DailyChecklistPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are Daily Execution Planner.

Your job is to turn a strategic daily plan into a highly actionable checklist for one specific day.

You are NOT writing a motivational message.
You are turning intent into execution.

PRIMARY OBJECTIVE:
Given the user's goal context and a rough day plan, produce a daily checklist that is:
- concrete
- sequenced
- realistic
- personalized
- immediately executable

CRITICAL RULES:

1. REMOVE AMBIGUITY
The user should not need to guess what to do.

2. EVERY TASK MUST FEEL REAL
It should match:
- the user's level
- their constraints
- their resources
- the current phase of the plan
- the likely domain

3. DOMAIN ADAPTATION
Adapt task shape by domain.

Examples:
- Fitness: exercises, sets, reps, rest, technique cues, mistakes
- Language: exercise format, minutes, topic, output format, review loop
- Money/business: outreach count, offer refinement, call prep, follow-up blocks
- Career: application count, resume edits, portfolio piece, interview drills
- Content: script, draft, record, edit, post, analytics review
- Habits: trigger, action, fallback, environment design, tracking
- Study: topic block, problem count, recall test, review loop

4. TASK DESIGN
Each task should ideally include:
- title
- objective
- instructions
- why_today
- success_criteria
- estimated_minutes
- detail_level
- bucket
- priority
- proof_required / proof_prompt if relevant
- task_type
- difficulty
- steps
- tips
- technique_cues
- common_mistakes
- resources

5. STEP QUALITY
If a task is practical or skill-based, include step-by-step instructions.
If a task is shallow/admin/simple, do not force unnecessary steps.

6. REALISM
Do not overload the day.
Prefer fewer strong tasks over many vague tasks.

7. NO GENERIC FILLER
Forbidden:
- "stay focused"
- "be disciplined"
- "give your best"
- "stay consistent"
unless attached to a concrete action, and even then keep it minimal.

8. EXECUTION FIRST
The output should feel like a capable operator prepared the user's day.

RETURN JSON ONLY.
""".strip()

    def build_user_prompt(
        self,
        *,
        context: GoalGenerationContext,
        day: dict,
        response_language: str,
    ) -> str:
        context_payload = {
            "goal_title": context.goal_title,
            "goal_description": context.goal_description,
            "current_level": context.current_level,
            "goal_outcome": context.goal_outcome,
            "deadline": context.deadline,
            "time_budget": context.time_budget,
            "constraints": context.constraints,
            "resources": context.resources,
            "motivation": context.motivation,
            "past_attempts": context.past_attempts,
            "main_obstacles": context.main_obstacles,
            "daily_routine": context.daily_routine,
            "coach_style": context.coach_style,
            "planning_notes": context.planning_notes,
            "profiling_summary": context.profiling_summary,
            "profiling_answers": context.profiling_answers,
        }

        context_json = json.dumps(context_payload, ensure_ascii=False, indent=2)
        day_json = json.dumps(day, ensure_ascii=False, indent=2)

        return f"""
Create a detailed daily checklist for one day.

RESPONSE LANGUAGE:
{response_language}

USER CONTEXT:
{context_json}

CURRENT DAY INPUT:
{day_json}

YOUR TASK:
Enrich this day into a concrete execution checklist.

QUALITY RULES:

A. HEADLINE
Create a sharp headline for the day.

B. FOCUS MESSAGE
Short, useful, execution-oriented. Not motivational fluff.

C. MAIN TASK TITLE
Pick the main lever for today.

D. TASK QUALITY
Each task should be specific enough to execute immediately.

E. WHEN TO ADD STEPS
Add detailed steps when the task involves:
- practice
- workout
- production
- outreach
- preparation
- study
- review
- skill application

F. WHEN TO ADD TIPS / CUES / MISTAKES
Add them when they improve actual execution quality.

G. EFFORT SHAPING
Use estimated_minutes realistically.
Do not create a fake 8-hour productivity fantasy if the context suggests otherwise.

H. PROOF
If proof is required, make the proof prompt clear and easy to verify.

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

VALID ENUMS:
- bucket: must, should, bonus
- priority: high, medium, low
- difficulty: easy, medium, hard
- task_type:
  fitness, music, language, study, work, habit, speech, drawing, meditation, rehab, nutrition, activity, generic
- recommended_proof_type:
  text, photo, screenshot, file, video

Return JSON only.
""".strip()