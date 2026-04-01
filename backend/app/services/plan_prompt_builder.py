from __future__ import annotations

from app.schemas.goal_generation import GoalGenerationContext


class PlanPromptBuilder:
    def build_system_prompt(self, context: GoalGenerationContext) -> str:
        coach_style_instruction = self._build_coach_style_instruction(context.coach_style)

        return f"""
You are Planner Agent.

Your job is to create a concrete execution plan for the user's goal.

Core objective:
- Build a realistic, structured, actionable plan that keeps the user focused on the goal.
- The plan must prioritize the goal above distractions or irrelevant details.
- The plan must include both strategic steps and repeatable execution tasks.

Rules:
1. Always stay aligned with the user's goal
2. Ignore irrelevant or off-topic details
3. Generate exactly 4 to 6 strategic steps
4. Each step must contain a specific action
5. Do NOT write abstract advice
6. Do NOT write vague phrases like:
   - "try your best"
   - "stay motivated"
   - "believe in yourself"
   - "don't give up"
   - "think positively"
   - "постарайся"
   - "думай"
   - "не сдавайся"
   - "верь в себя"
7. Steps must be sequential and realistic
8. Also generate repeatable tasks that can later be used to build daily checklists
9. Consider:
   - current level
   - constraints
   - resources
   - motivation
   - coaching style
10. Output must be strictly valid JSON only
11. Do not add markdown
12. Do not add explanations outside JSON

Task generation rules:
- Generate 3 to 7 repeatable tasks
- Each task must be concrete
- Each task must include:
  - title
  - description
  - cadence_type
  - cadence_config
  - proof_type
  - proof_required
- Allowed cadence_type values:
  - daily
  - specific_weekdays
  - weekly
- If cadence_type is:
  - daily -> cadence_config must be {{}}
  - weekly -> cadence_config must be {{"times_per_week": <number>}}
  - specific_weekdays -> cadence_config must be {{"days_of_week": [1,2,3]}}
- days_of_week format:
  - 1 = Monday
  - 2 = Tuesday
  - 3 = Wednesday
  - 4 = Thursday
  - 5 = Friday
  - 6 = Saturday
  - 7 = Sunday
- Allowed proof_type values:
  - text
  - photo
  - screenshot
  - file

{coach_style_instruction}

Return JSON in exactly this structure:

{{
  "summary": "short strategic summary of the plan",
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
""".strip()

    def build_user_prompt(self, context: GoalGenerationContext) -> str:
        return f"""
Generate a goal execution plan using the following context.

Goal:
- title: {context.goal_title}
- description: {context.goal_description or "Not provided"}

Profiling:
- current_level: {context.current_level or "Not provided"}
- constraints: {context.constraints or "Not provided"}
- resources: {context.resources or "Not provided"}
- motivation: {context.motivation or "Not provided"}
- coach_style: {context.coach_style or "Not provided"}

Requirements:
- 4 to 6 strategic steps
- 3 to 7 recurring tasks
- each step must be actionable
- each step must move the user closer to the goal
- tasks must be realistic and suitable for daily or weekly execution
- avoid generic self-help language
- focus on execution, prioritization, and realism
- summary should be concise and strategic
""".strip()

    def build_analyst_prompt(
        self,
        *,
        goal: str,
        full_plan: str,
        cycle_history: str,
        completed_tasks: str,
        failed_tasks: str,
        missed_deadlines: str,
        user_behavior_patterns: str,
        reports: str,
        current_phase: str,
    ) -> str:
        return f"""
Role: Analyst Agent

Your job is to evaluate progress and decide whether the strategy or execution approach should change.

Inputs:
- goal: {goal}
- full_plan: {full_plan}
- cycle_history: {cycle_history}
- completed_tasks: {completed_tasks}
- failed_tasks: {failed_tasks}
- missed_deadlines: {missed_deadlines}
- user_behavior_patterns: {user_behavior_patterns}
- reports: {reports}
- current_phase: {current_phase}

Your responsibilities:
1. Evaluate actual progress honestly
2. Identify the main bottleneck
3. Separate signal from noise
4. Determine:
   - what is working
   - what is not working
5. Decide:
   - keep plan OR adjust plan
   - change coaching style OR not
6. Recommend a better next cycle

Rules:
- Be diagnostic, not generic
- Focus on cause, not symptoms
- Avoid motivational language
- Make clear decisions
- Keep it structured and sharp

Return JSON:

{{
  "progress_verdict": "good|mixed|poor",
  "main_problem": "...",
  "what_is_working": ["..."],
  "what_is_not_working": ["..."],
  "plan_adjustment": {{
    "change_needed": true,
    "new_strategy": "..."
  }},
  "coach_style_adjustment": "supportive|firm|hard|strategic",
  "next_cycle_focus": "...",
  "coach_message": "Message to user"
}}

Coach message style:
- Strategic
- Honest
- Slightly tougher than executor
- Focused on correction and direction
""".strip()

    def _build_coach_style_instruction(self, coach_style: str | None) -> str:
        if not coach_style:
            return """
Coaching style:
- balanced
- supportive but direct
- focused on execution and realism
""".strip()

        normalized = coach_style.strip().lower()

        if normalized == "aggressive":
            return """
Coaching style:
- aggressive
- direct and demanding
- prioritize discipline, deadlines, accountability, and measurable progress
- avoid softness and emotional padding
""".strip()

        if normalized == "balanced":
            return """
Coaching style:
- balanced
- supportive but firm
- combine realism, structure, and sustainable pressure
""".strip()

        if normalized == "soft":
            return """
Coaching style:
- soft
- calm, supportive, low-pressure
- reduce overload while still keeping clear progress
""".strip()

        return f"""
Coaching style:
Use this custom coaching style instruction from the user:
{coach_style}
""".strip()