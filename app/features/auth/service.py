from datetime import datetime, timedelta, timezone
import secrets

import httpx
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginIn, SignupIn, UpdateMeIn, normalize_email

_ALGO = "HS256"
_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


async def create_user(db: AsyncSession, data: SignupIn) -> User:
    existing = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if existing is not None:
        raise ValueError("email_taken")
    user = User(full_name=data.full_name, email=data.email, password_hash=hash_password(data.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user(db: AsyncSession, user: User, data: UpdateMeIn) -> User:
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.avatar is not None:
        # Empty string clears the avatar; any other value is stored as-is.
        user.avatar = data.avatar or None
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate(db: AsyncSession, data: LoginIn) -> User | None:
    user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if user is None or not verify_password(data.password, user.password_hash):
        return None
    return user


def create_oauth_state() -> str:
    settings = get_settings()
    payload = {
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGO)


def verify_oauth_state(state: str) -> bool:
    try:
        jwt.decode(state, get_settings().jwt_secret, algorithms=[_ALGO])
        return True
    except JWTError:
        return False


def google_auth_url(state: str) -> str:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google sign-in is not configured")
    params = httpx.QueryParams({
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    })
    return f"{_GOOGLE_AUTH_URL}?{params}"


async def authenticate_google(db: AsyncSession, code: str) -> User:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise RuntimeError("Google sign-in is not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        token_resp = await client.post(
            _GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        if token_resp.status_code >= 400:
            raise RuntimeError("Google sign-in failed")

        access_token = token_resp.json().get("access_token")
        if not access_token:
            raise RuntimeError("Google sign-in failed")

        profile_resp = await client.get(
            _GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if profile_resp.status_code >= 400:
            raise RuntimeError("Could not read Google profile")

    profile = profile_resp.json()
    if profile.get("email_verified") is False:
        raise RuntimeError("Google email is not verified")

    email = normalize_email(str(profile.get("email", "")))
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is not None:
        return user

    full_name = str(profile.get("name") or email.split("@", 1)[0]).strip()
    user = User(
        full_name=full_name or email,
        email=email,
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
