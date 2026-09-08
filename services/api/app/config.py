from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
