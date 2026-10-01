"""Privacy consent and AI personalisation (P3.7).

The AI features (Ciel, the hypothesis check, explain-back questions and
scoring) send the student's work to OpenAI, so they need consent to the
current policy version. Changing the policy text means a new POLICY_VERSION,
and everyone is asked again.
"""
from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.models import User

POLICY_VERSION = "2026-10"
CONSENT_REQUIRED = {
    "code": "privacy_consent_required",
    "message_vi": "Bạn cần đồng ý với Chính sách quyền riêng tư trước khi dùng các tính năng AI.",
    "message_en": "Please accept the Privacy Policy before using the AI features.",
}


def has_consent(user: User) -> bool:
    return user.privacy_consent_at is not None and user.privacy_version == POLICY_VERSION


def require_consent(user: User) -> None:
    if not has_consent(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=CONSENT_REQUIRED)


def record_consent(user: User) -> None:
    user.privacy_consent_at = datetime.now(timezone.utc)
    user.privacy_version = POLICY_VERSION
