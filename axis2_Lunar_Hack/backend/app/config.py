from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Adaptive AI Decision Engine"
    environment: str = "development"
    debug: bool = False

    ollama_base_url: str = "http://localhost:11434"
    ollama_model_fast: str = "mistral"
    ollama_model_reasoning: str = "llama3"
    agent_json_repair_retry: bool = True
    intent_use_reasoning_model: bool = False
    schema_builder_use_reasoning_model: bool = False
    qualification_use_reasoning_model: bool = False
    rag_use_reasoning_model: bool = False
    recommendation_use_reasoning_model: bool = False
    finalization_use_reasoning_model: bool = False
    single_generation_use_reasoning_model: bool = False

    ragflow_base_url: str = "http://localhost:9380"
    ragflow_api_key: str = ""
    ragflow_dataset_ids: str = Field(default="sales-kb")
    ragflow_top_k: int = 5

    sqlite_path: str = "data/sales_memory.db"
    max_context_turns: int = 10
    default_language: str = "en"

    allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5175,http://127.0.0.1:5175,http://localhost:5176,http://127.0.0.1:5176"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def rag_dataset_list(self) -> List[str]:
        return [dataset.strip() for dataset in self.ragflow_dataset_ids.split(",") if dataset.strip()]

    @property
    def cors_origins(self) -> List[str]:
        configured = [origin.strip() for origin in self.allow_origins.split(",") if origin.strip()]
        defaults = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5175",
            "http://127.0.0.1:5175",
            "http://localhost:5176",
            "http://127.0.0.1:5176",
        ]
        return list(dict.fromkeys([*configured, *defaults]))


@lru_cache
def get_settings() -> Settings:
    return Settings()
