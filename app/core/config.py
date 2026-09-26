from functools import lru_cache
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://codeprove:codeprove@localhost:5432/codeprove"
    jwt_secret: str = "change-me"
    jwt_expire_minutes: int = 10080
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    frontend_url: str = "http://localhost:3000"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/auth/google/callback"
    # NoDecode skips pydantic-settings' JSON decoding so split_origins below
    # parses a comma-separated string straight from the .env value.
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:3000"]
    sandbox_timeout: int = 5
    # Per-user cap on sandbox executions (trace + run) per minute.
    sandbox_rate_limit_per_minute: int = 20
    # Shared-secret for the daily-challenge regenerate ops endpoint. Empty by
    # default so the endpoint is a no-op (always 403) until an operator sets
    # it - there is no user-role/admin system in this codebase to hook into.
    admin_api_key: str = ""
    # Which scoring engine writes new reports. v2 (rubric levels, P1.4) replaces
    # v1 only after it beats v1 on the golden set (see the P1.4 plan, Task 7).
    scoring_engine: Literal["v1", "v2"] = "v1"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
