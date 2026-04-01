class ProfilingQuestionPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are Profiling Question Agent.

Your task is to generate exactly 5 short, high-impact profiling questions
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

You MUST include exactly these keys, once each:
- current_level
- constraints
- resources
- motivation
- time_budget

Do NOT include coach_style. It will be added separately by the backend.

The wording of each question should adapt to the goal,
but the keys must remain exactly the same.

Return JSON:
{
  "questions": [
    {
      "id": "q1",
      "key": "current_level",
      "text": "..."
    },
    {
      "id": "q2",
      "key": "constraints",
      "text": "..."
    },
    {
      "id": "q3",
      "key": "resources",
      "text": "..."
    },
    {
      "id": "q4",
      "key": "motivation",
      "text": "..."
    },
    {
      "id": "q5",
      "key": "time_budget",
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

Important:
Generate questions whose wording is tailored to this goal,
but keep the keys exactly as required.
""".strip()