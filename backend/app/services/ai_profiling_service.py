from app.services.openai_client import OpenAIClient
from app.services.profiling_prompt_builder import ProfilingPromptBuilder
from app.config import settings


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