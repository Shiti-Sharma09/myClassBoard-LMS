"""Application settings, read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # In Docker the values come from the environment; locally they come from the repo-root .env.
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    # --- AI provider ---
    groq_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_model_main: str = "openai/gpt-oss-120b"
    llm_model_fast: str = "openai/gpt-oss-20b"
    vision_model: str = "qwen/qwen3.8-27b"
    # Only sent to reasoning models (gpt-oss). Lower is faster.
    llm_reasoning_effort: str = "low"
    ai_timeout_s: float = 60.0
    ai_max_retries: int = 2  # re-asks after invalid output
    ai_max_transport_retries: int = 3  # retries on 429 / 5xx / timeouts

    # --- App ---
    database_url: str = "postgresql+psycopg://lms:lms@db:5432/lms"
    jwt_secret: str = "dev-only-secret-change-me-before-any-real-use"
    jwt_expire_minutes: int = 720
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "/app/uploads"
    # Shows demo login buttons. POC only: turn off for anything real.
    demo_mode: bool = True

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
