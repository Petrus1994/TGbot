from app.config import settings
from app.services.openai_client import OpenAIClient
from app.services.profiling_prompt_builder import ProfilingPromptBuilder


class AIProfilingService:
    def __init__(self):
        self.prompt_builder = ProfilingPromptBuilder()
        self.llm = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def generate_questions(self, goal: str) -> dict:
        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(goal)

        return await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def judge_answer(
        self,
        goal_title: str,
        goal_description: str | None,
        question: dict,
        user_answer: str,
        answers: dict[str, str],
    ) -> dict:
        system_prompt = self.prompt_builder.build_answer_judge_system_prompt()
        user_prompt = self.prompt_builder.build_answer_judge_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            question_key=question.get("key", ""),
            question_text=question.get("text", ""),
            example_answer=question.get("example_answer"),
            user_answer=user_answer,
            answers=answers,
            suggested_options=question.get("suggested_options"),
        )

        return await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def select_next_question(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
        candidate_questions: list[dict],
    ) -> dict:
        system_prompt = self.prompt_builder.build_next_question_selector_system_prompt()
        user_prompt = self.prompt_builder.build_next_question_selector_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            answers=answers,
            candidate_questions=candidate_questions,
        )

        return await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

    async def build_profiling_summary(
        self,
        goal_title: str,
        goal_description: str | None,
        answers: dict[str, str],
    ) -> dict:
        system_prompt = self.prompt_builder.build_profiling_summary_system_prompt()
        user_prompt = self.prompt_builder.build_profiling_summary_user_prompt(
            goal_title=goal_title,
            goal_description=goal_description,
            answers=answers,
        )

        return await self.llm.generate_plan(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )