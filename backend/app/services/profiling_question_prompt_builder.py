class ProfilingQuestionPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are Profiling Question Agent.

Your task is to generate 5 to 7 short, high-impact profiling questions
that will help create the most effective plan for the user's goal.

Rules:
- Questions must depend on the goal
- Questions must be specific and practical
- Avoid generic fluff
- Avoid duplicate meaning
- Use concise language
- Return JSON only
- Each question must have:
  - id
  - key
  - text

Allowed keys:
- current_level
- constraints
- resources
- time_budget
- motivation
- deadline
- habits
- environment
- experience_level

Do NOT include coach_style. It will be added separately by the backend.

Return JSON:
{
  "questions": [
    {
      "id": "q1",
      "key": "current_level",
      "text": "..."
    }
  ]
}
""".strip()

    def build_user_prompt(
        self,
        *,
        goal_title: str,
        goal_description: str | None,
        goal_analysis: dict,
    ) -> str:
        return f"""
Goal title:
{goal_title}

Goal description:
{goal_description or "Not provided"}

Goal analysis:
{goal_analysis}
""".strip()