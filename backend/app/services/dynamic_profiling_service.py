from __future__ import annotations

from app.config import settings
from app.schemas.profiling_dynamic import (
    GoalAnalysisSchema,
    ProfilingQuestionListSchema,
    ProfilingQuestionSchema,
)
from app.services.goal_analysis_prompt_builder import GoalAnalysisPromptBuilder
from app.services.openai_client import OpenAIClient
from app.services.profiling_question_prompt_builder import ProfilingQuestionPromptBuilder


class DynamicProfilingService:
    def __init__(self) -> None:
        self.goal_analysis_prompt_builder = GoalAnalysisPromptBuilder()
        self.question_prompt_builder = ProfilingQuestionPromptBuilder()
        self.llm = OpenAIClient(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
        )

    async def build_context(
        self,
        *,
        goal_title: str,
        goal_description: str | None = None,
    ) -> dict:
        goal_analysis_raw = await self.llm.generate_plan(
            system_prompt=self.goal_analysis_prompt_builder.build_system_prompt(),
            user_prompt=self.goal_analysis_prompt_builder.build_user_prompt(
                goal_title=goal_title,
                goal_description=goal_description,
            ),
        )
        goal_analysis = GoalAnalysisSchema.model_validate(goal_analysis_raw)

        questions_raw = await self.llm.generate_plan(
            system_prompt=self.question_prompt_builder.build_system_prompt(),
            user_prompt=self.question_prompt_builder.build_user_prompt(
                goal_title=goal_title,
                goal_description=goal_description,
                goal_analysis=goal_analysis.model_dump(),
            ),
        )
        parsed_questions = ProfilingQuestionListSchema.model_validate(questions_raw)

        questions = list(parsed_questions.questions)

        questions.append(
            ProfilingQuestionSchema(
                id=f"q{len(questions) + 1}",
                key="coach_style",
                text="Какой стиль коучинга тебе подходит? aggressive / balanced / soft / или опиши свой вариант.",
            )
        )

        return {
            "profiling": {
                "mode": "dynamic_ai",
                "goal_analysis": goal_analysis.model_dump(),
                "questions": [q.model_dump() for q in questions],
                "answers": {},
                "current_question_index": 0,
                "is_completed": False,
                "questions_total_count": len(questions),
                "questions_answered_count": 0,
            }
        }