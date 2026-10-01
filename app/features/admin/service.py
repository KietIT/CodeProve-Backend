"""Admin-only authentication and audit helpers; never return stored password hashes."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import AdminAuditLog, AdminSession, User

COOKIE = "codeprove_admin_session"
SESSION_HOURS = 12


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def require_frontend_origin(request: Request) -> None:
    origin = request.headers.get("origin", "").rstrip("/")
    settings = get_settings()
    allowed = {settings.frontend_url.rstrip("/"), *(o.rstrip("/") for o in settings.cors_origins)}
    if origin not in allowed:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Untrusted request origin")


def set_cookie(response: Response, token: str) -> None:
    settings = get_settings()
    response.set_cookie(
        COOKIE, token, max_age=SESSION_HOURS * 3600, path="/api", httponly=True,
        secure=settings.frontend_url.startswith("https://"), samesite=settings.admin_cookie_samesite,
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/api")


async def create_session(db: AsyncSession, user: User, response: Response) -> None:
    token = secrets.token_urlsafe(32)
    current = now_utc()
    db.add(AdminSession(
        user_id=user.id, token_hash=sha256(token.encode()).hexdigest(),
        expires_at=current + timedelta(hours=SESSION_HOURS), last_seen_at=current,
    ))
    await db.commit()
    set_cookie(response, token)


async def revoke_sessions(db: AsyncSession, user_id: int) -> None:
    await db.execute(update(AdminSession).where(
        AdminSession.user_id == user_id, AdminSession.revoked_at.is_(None)
    ).values(revoked_at=now_utc()))


def log(db: AsyncSession, action: str, actor: int | None, target: int | None, detail: str | None = None) -> None:
    db.add(AdminAuditLog(actor_user_id=actor, target_user_id=target, action=action, detail=detail))


def temporary_password() -> str:
    return secrets.token_urlsafe(24)
