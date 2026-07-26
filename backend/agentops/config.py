from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "AgentOps Studio API"
    app_env: Literal["development", "test", "production"] = "development"
    seed_demo_data: bool = True
    api_prefix: str = "/api/v1"
    database_url: str = "sqlite+aiosqlite:///./agentops.db"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    agent_provider: Literal["mock", "openai"] = "mock"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.6-terra"
    openai_store_responses: bool = False

    max_agent_steps: int = Field(default=8, ge=1, le=32)
    max_repeated_tool_calls: int = Field(default=2, ge=1, le=8)
    tool_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    tool_retry_attempts: int = Field(default=1, ge=0, le=3)
    run_timeout_seconds: float = Field(default=30.0, gt=1, le=300)
    run_budget_usd: float = Field(default=0.25, gt=0, le=100)

    otel_service_name: str = "agentops-studio-api"
    otel_exporter_otlp_endpoint: str | None = None
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
