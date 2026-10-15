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
    # Use "none" with HTTPS when frontend and API are on different sites.
    admin_cookie_samesite: Literal["lax", "none"] = "lax"
    # Which scoring engine writes new reports. v2 (rubric levels, P1.4) replaces
    # v1 only after it beats v1 on the golden set (see the P1.4 plan, Task 7).
    scoring_engine: Literal["v1", "v2"] = "v1"
    # LLM cost caps per student (P3.6). One student message counts once, guard retries included.
    ciel_per_attempt: int = 30
    # Ciel messages per day by plan: ciel_per_day is the Free limit.
    ciel_per_day: int = 20
    ciel_per_day_plus: int = 100
    ciel_per_day_pro: int = 200
    # Submitted attempts per calendar month on the Free plan (paid plans are unlimited).
    free_submits_per_month: int = 10
    ciel_per_minute: int = 10
    hypothesis_per_attempt: int = 10
    # Hard caps on code Ciel may show (fix 2026-10-01), counting only lines that are not already in the
    # student's own code or the served starter: per reply, and distinct lines over the whole attempt.
    ciel_max_code_lines_per_reply: int = 3
    ciel_max_code_lines_per_attempt: int = 8
    quota_timezone: str = "Asia/Ho_Chi_Minh"  # the "day" of ciel_per_day
    # USD per million tokens for the cost report (P3.6). Copy them from OpenAI's pricing page for
    # openai_model; 0 = not set, and the report then shows tokens without a cost.
    openai_price_input_per_m: float = 0.0
    openai_price_cached_per_m: float = 0.0
    openai_price_output_per_m: float = 0.0
    # SePay (payments by bank transfer). Empty key or account = payments disabled: checkout answers 503 and
    # the webhook rejects everything. The key is the one typed into SePay's webhook form ("API Key").
    sepay_api_key: str = ""
    sepay_bank_account: str = ""  # the account linked in SePay that receives the money
    sepay_bank_name: str = ""  # short name as VietQR knows it, e.g. TPBank
    sepay_account_name: str = ""  # holder name shown to the student
    # Transfer content is this prefix + the order id. Must match the payment-code prefix set in SePay.
    sepay_code_prefix: str = "CP"
    sepay_qr_url: str = "https://qr.sepay.vn/img"
    # An order not paid within this many minutes is shown as expired (a late transfer is still honoured).
    payment_window_minutes: int = 15
    checkout_per_minute: int = 5
    # Google Analytics 4: the server reports paid orders as `purchase` (analytics/ga4.py). Both empty = off.
    # Measurement ID "G-..." of the web stream; API secret from GA4 Admin > Data streams > the web stream >
    # Measurement Protocol API secrets. Never commit the secret.
    ga_measurement_id: str = ""
    ga_api_secret: str = ""

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
