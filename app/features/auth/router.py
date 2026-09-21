from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.features.auth import service
from app.models import User
from app.schemas.auth import AuthOut, LoginIn, SignupIn, UpdateMeIn, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _allowed_frontend_origins() -> set[str]:
    settings = get_settings()
    origins = {o.rstrip("/") for o in settings.cors_origins}
    origins.add(settings.frontend_url.rstrip("/"))
    return origins


def _validate_frontend_origin(url: str | None) -> str | None:
    """Return scheme://host[:port] of `url` if it is an allowlisted frontend
    origin, else None. Guards against open-redirect - only the origin is used,
    the path is always the fixed /auth/callback below."""
    if not url:
        return None
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return None
    origin = f"{parts.scheme}://{parts.netloc}"
    return origin if origin in _allowed_frontend_origins() else None


def _frontend_callback_url(base: str, token: str | None = None, error: str | None = None) -> str:
    params = []
    if token:
        params.append(("token", token))
    if error:
        params.append(("error", error))
    query = urlencode(params)
    return f"{base.rstrip('/')}/auth/callback{f'?{query}' if query else ''}"


@router.post("/signup", response_model=AuthOut)
async def signup(data: SignupIn, db: AsyncSession = Depends(get_db)) -> AuthOut:
    try:
        user = await service.create_user(db, data)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return AuthOut(user=UserOut.model_validate(user, from_attributes=True), access_token=create_access_token(str(user.id)))


@router.post("/login", response_model=AuthOut)
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)) -> AuthOut:
    user = await service.authenticate(db, data)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AuthOut(user=UserOut.model_validate(user, from_attributes=True), access_token=create_access_token(str(user.id)))


@router.get("/google/start")
async def google_start(redirect: str | None = None) -> RedirectResponse:
    # Validated caller origin (localhost in dev, deployed URL in prod); carried
    # through Google via the signed state so the callback returns to it.
    origin = _validate_frontend_origin(redirect)
    fallback = get_settings().frontend_url
    try:
        url = service.google_auth_url(service.create_oauth_state(origin))
    except RuntimeError as exc:
        return RedirectResponse(_frontend_callback_url(origin or fallback, error=str(exc)))
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    payload = service.decode_oauth_state(state) if state else None
    # Re-validate the origin from the signed state (defense in depth).
    base = (_validate_frontend_origin(payload.get("redirect")) if payload else None) or get_settings().frontend_url
    if error:
        return RedirectResponse(_frontend_callback_url(base, error=error))
    if not code or payload is None:
        return RedirectResponse(_frontend_callback_url(base, error="Invalid Google sign-in response"))
    try:
        user = await service.authenticate_google(db, code)
    except (RuntimeError, ValueError) as exc:
        return RedirectResponse(_frontend_callback_url(base, error=str(exc)))
    return RedirectResponse(_frontend_callback_url(base, token=create_access_token(str(user.id))))


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.model_validate(user, from_attributes=True)


@router.patch("/me", response_model=UserOut)
async def update_me(
    data: UpdateMeIn,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> UserOut:
    updated = await service.update_user(db, user, data)
    return UserOut.model_validate(updated, from_attributes=True)
