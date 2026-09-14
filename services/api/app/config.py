from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"
    database_url: str = "postgresql+psycopg://shelfready:shelfready@localhost:55433/shelfready"
    shelfready_api_token: str = "dev-token-change-me"
    agent_mode: Literal["live", "replay"] = "replay"
    aws_region: str = "us-west-2"
    bedrock_model_id: str = "global.anthropic.claude-sonnet-4-6"
    storage_root: Path = Path("./storage")
    fixtures_root: Path = Path("./fixtures")
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:3001"
    workspace_name: str = "Demo Store"
    currency_default: str = "USD"
    lookup_provider: Literal["upcitemdb", "replay"] = "replay"
    upcitemdb_api_key: str = ""
    lookup_budget_per_run: int = 25
    lookup_timeout_seconds: float = 10.0
    lookup_max_retries: int = 2

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @model_validator(mode="after")
    def reject_production_localhost(self) -> "Settings":
        if self.environment != "production":
            return self
        host = self.database_url.lower()
        if "localhost" in host or "127.0.0.1" in host:
            raise ValueError(
                "Production DATABASE_URL must not use localhost or 127.0.0.1. "
                "Point it at the separately hosted Postgres instance."
            )
        if self.shelfready_api_token in {"", "dev-token-change-me"}:
            raise ValueError(
                "Production SHELFREADY_API_TOKEN must be set to a non-default secret. "
                "Do not expose it as NEXT_PUBLIC_API_TOKEN."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
