from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://codeprove:codeprove@localhost:5432/codeprove"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 10080
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    # NoDecode skips pydantic-settings' JSON decoding so split_origins below
    # parses a comma-separated string straight from the .env value.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    sandbox_timeout: int = 5

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
