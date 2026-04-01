class GoalAnalysisPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are Goal Analysis Agent.

Your task is to analyze the user's goal and determine:
- goal_type
- difficulty
- time_horizon
- what profiling information is most important to collect

Return valid JSON only.

Allowed profiling_focus keys:
- current_level
- constraints
- resources
- time_budget
- motivation
- deadline
- habits
- environment
- experience_level

Return JSON in this format:
{
  "goal_type": "fitness|education|career|business|coding|discipline|custom",
  "difficulty": "low|medium|high",
  "time_horizon": "short|medium|long",
  "profiling_focus": ["current_level", "constraints", "time_budget"]
}
""".strip()

    def build_user_prompt(
        self,
        *,
        goal_title: str,
        goal_description: str | None = None,
    ) -> str:
        return f"""
User goal title:
{goal_title}

User goal description:
{goal_description or "Not provided"}
""".strip()