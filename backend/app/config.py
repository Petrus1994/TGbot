from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    openai_api_key: str = ""

    openai_model_mini: str = "gpt-4.1-mini"
    openai_model_reasoning: str = "gpt-5.4"

    ai_plan_model: str = "gpt-5.4"
    ai_analysis_model: str = "gpt-5.4"
    ai_executor_model: str = "gpt-4.1-mini"
    ai_coach_model: str = "gpt-4.1-mini"
    ai_plan_generation_enabled: bool = True
    ai_plan_fallback_to_stub: bool = True

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()