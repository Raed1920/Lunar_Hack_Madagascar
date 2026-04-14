from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    app_name: str = "Marketing AI Assistant Backend"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    postgres_host: str = "localhost"
    postgres_port: int = 55432
    postgres_db: str = "marketing_ai_dev"
    postgres_user: str = "marketing_user"
    postgres_password: str = "marketing_pwd_local"
    database_url: str = Field(
        default="postgresql+psycopg://marketing_user:marketing_pwd_local@localhost:55432/marketing_ai_dev"
    )

    db_pool_min_size: int = 1
    db_pool_max_size: int = 5

    default_workspace_id: str = "11111111-1111-1111-1111-111111111111"

    llm_primary_provider: str = "groq"
    llm_fallback_provider: str = "gemini"
    llm_timeout_seconds: int = 8
    llm_max_retries: int = 1
    llm_temperature: float = 0.2
    llm_top_p: float = 1.0
    llm_max_output_tokens: int = 1024

    groq_model: str = "llama-3.3-70b-versatile"
    gemini_model: str = "gemini-1.5-flash"

    groq_api_key: str | None = None
    gemini_api_key: str | None = None

    n8n_webhook_url: str | None = None
    n8n_webhook_token: str | None = None
    n8n_signal_webhook_url: str | None = None
    n8n_campaign_ops_webhook_url: str | None = None
    n8n_creative_media_webhook_url: str | None = None
    n8n_learning_webhook_url: str | None = None
    n8n_publish_webhook_url: str | None = None
    n8n_request_timeout_seconds: float = 3.5

    model_config = SettingsConfigDict(
        env_file=(str(ROOT_DIR / ".env.example"), str(ROOT_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
