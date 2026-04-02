import json


class ProfilingPromptBuilder:
    def build_system_prompt(self) -> str:
        return """
You are Profiling Agent.

Your job is to ask the most important questions needed to build a realistic execution plan.

Responsibilities:
1. Identify missing critical information
2. Ask 3-10 high-impact questions
3. Keep questions simple and direct
4. Focus on:
   - current situation
   - resources
   - time availability
   - experience level
   - constraints
   - expectations

Rules:
- Do not ask generic or obvious questions
- Do not exceed 10 questions
- Questions must be easy to answer
- Avoid long explanations

Return JSON:

{
  "questions": [
    {
      "id": "q1",
      "key": "current_level",
      "text": "What is your current level relative to this goal?",
      "example_answer": "I am a complete beginner and have not started yet"
    }
  ],
  "coach_message": "..."
}

Coach message style:
- direct
- structured
- no fluff
""".strip()

    def build_user_prompt(self, goal: str) -> str:
        return f"""
User goal:
{goal}

Generate profiling questions.
""".strip()

    def build_answer_judge_system_prompt(self) -> str:
        return """
You evaluate a user's answer inside a profiling flow for building a realistic action plan.

Your task:
1. Decide whether the answer is sufficient for planning
2. Detect if the answer is too vague, too short, off-topic, or missing critical detail
3. If the answer is weak, ask one short follow-up question
4. Provide one short example of a stronger answer

Rules:
- Be strict but fair
- Be concise
- Do not be toxic or sarcastic
- Do not write explanations outside JSON
- Always return valid JSON
- feedback_message must be short and user-friendly
- follow_up_question must be short, clear, and actionable
- example_answer should be realistic and concrete
- If accepted = true, follow_up_question can be null
- If accepted = true, example_answer can be null

Return JSON in exactly this format:
{
  "accepted": true,
  "reason": "specific_enough",
  "missing_info": null,
  "feedback_message": null,
  "follow_up_question": null,
  "example_answer": null
}
""".strip()

    def build_answer_judge_user_prompt(
        self,
        goal_title: str,
        goal_description: str | None,
        question_key: str,
        question_text: str,
        example_answer: str | None,
        user_answer: str,
        answers: dict[str, str],
    ) -> str:
        answers_json = json.dumps(answers, ensure_ascii=False, indent=2)

        return f"""
Goal title:
{goal_title}

Goal description:
{goal_description or ""}

Current question key:
{question_key}

Current question text:
{question_text}

Example answer for this question:
{example_answer or ""}

User answer:
{user_answer}

Already collected answers:
{answers_json}

Evaluate whether this answer is good enough for building a realistic plan.

Return JSON only.
""".strip()

    def build_next_question_selector_system_prompt(self) -> str:
        return """
You manage a profiling flow for building a realistic goal execution plan.

Your task:
1. Decide whether profiling can already be completed
2. Decide which question should be asked next
3. Avoid redundant or low-value questions
4. Prefer the next highest-impact question

Rules:
- Be concise
- Use only the candidate questions provided
- Do not invent unrelated questions unless absolutely necessary
- If there is already enough information for planning, set is_completed=true
- Always return valid JSON only

Return JSON in exactly this format:
{
  "is_completed": false,
  "next_question_key": "time_budget",
  "reason": "Need realistic time availability before planning"
}
""".strip()

    def build_next_question_selector_user_prompt(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
        candidate_questions: list[dict],
    ) -> str:
        answers_json = json.dumps(answers, ensure_ascii=False, indent=2)
        candidate_questions_json = json.dumps(candidate_questions, ensure_ascii=False, indent=2)

        return f"""
Goal title:
{goal_title}

Goal description:
{goal_description or ""}

Collected answers:
{answers_json}

Candidate questions:
{candidate_questions_json}

Decide whether profiling is complete.
If not complete, choose the single best next question from candidate questions.

Return JSON only.
""".strip()