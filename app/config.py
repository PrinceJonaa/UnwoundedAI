from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    api_title: str = "Unwounded AI Runtime"
    api_version: str = "0.1.0"

    litellm_model: str = "gpt-4o-mini"
    litellm_temperature: float = 0.2

    database_url: str | None = None

    mem0_enabled: bool = False
    mem0_api_key: str | None = None

    braintrust_enabled: bool = False
    braintrust_project: str = "unwounded-ai"
    braintrust_api_key: str | None = None

    langsmith_enabled: bool = False
    langsmith_project: str = "unwounded-ai"

    search_provider: Literal["duckduckgo", "tavily", "none"] = "duckduckgo"
    tavily_api_key: str | None = None
    search_max_results: int = 5
    search_timeout_seconds: float = 8.0

    max_retrieval_attempts: int = 2


class ModelSelection(BaseModel):
    model_name: str = Field(..., min_length=1)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


settings = RuntimeSettings()
