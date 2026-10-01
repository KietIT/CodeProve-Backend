"""Admin auth and super-admin account operations."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.db import get_db
from app.core.security import hash_password, verify_password
from app.features.admin import service
from app.models import AdminAuditLog, AdminSession, User
from app.schemas.auth import LoginIn, normalize_email

auth_router = APIRouter(prefix="/api/auth/admin", tags=["admin auth"])
router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminOut(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    must_change_password: bool
    last_login_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=15)

    @field_validator("new_password")
    @classmethod
    def valid_bcrypt_length(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class CreateAdminIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=255)
    email: str

    @field_validator("email")
    @classmethod
    def internal_email(cls, value: str) -> str:
        email = normalize_email(value)
        if not email.endswith("@codeprove.production"):
            raise ValueError("Use an internal admin login ID")
        return email


class SetStatusIn(BaseModel):
    is_active: bool


class TempPasswordOut(BaseModel):
    admin: AdminOut
    temporary_password: str


@dataclass
class Principal:
    user: User
    session: AdminSession


async def current_admin(request: Request, db: AsyncSession = Depends(get_db)) -> Principal:
    token = request.cookies.get(service.COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Admin session required")
    session = (await db.execute(select(AdminSession).where(
        AdminSession.token_hash == sha256(token.encode()).hexdigest()
    ))).scalar_one_or_none()
    now = service.now_utc()
    if session is None or session.revoked_at is not None or service.aware(session.expires_at) <= now:
        raise HTTPException(status_code=401, detail="Admin session expired")
    user = await db.get(User, session.user_id)
    if user is None or user.role not in ("admin", "super_admin") or not user.is_active:
        raise HTTPException(status_code=401, detail="Admin account unavailable")
    if service.aware(session.last_seen_at) < now - timedelta(seconds=60):
        session.last_seen_at = now
        await db.commit()
    return Principal(user, session)


async def ready_admin(principal: Principal = Depends(current_admin)) -> Principal:
    if principal.user.must_change_password:
        raise HTTPException(status_code=403, detail="Change your temporary password first")
    return principal


async def super_admin(principal: Principal = Depends(ready_admin)) -> Principal:
    if principal.user.role != "super_admin":
        raise HTTPException(status_code=403, detail="Super admin permission required")
    return principal


@auth_router.post("/login", response_model=AdminOut)
async def login(data: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)) -> AdminOut:
    service.require_frontend_origin(request)
    response.headers["Cache-Control"] = "no-store"
    # The existing limiter is process-local; use a shared store before multi-worker deployment.
    rate_limit.enforce(f"admin-login:{data.email}:{request.client.host if request.client else 'unknown'}", 10, 300)
    user = (await db.execute(select(User).where(User.email == data.email))).scalar_one_or_none()
    if user is None or user.role not in ("admin", "super_admin") or not user.is_active or not verify_password(data.password, user.password_hash):
        if user is not None and user.role in ("admin", "super_admin"):
            service.log(db, "login_failed", None, user.id)
            await db.commit()
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    user.last_login_at = service.now_utc()
    service.log(db, "login", user.id, user.id)
    await service.create_session(db, user, response)
    return AdminOut.model_validate(user)


@auth_router.get("/me", response_model=AdminOut)
async def me(principal: Principal = Depends(current_admin)) -> AdminOut:
    return AdminOut.model_validate(principal.user)


@auth_router.post("/change-password", response_model=AdminOut)
async def change_password(data: ChangePasswordIn, request: Request, response: Response,
                          principal: Principal = Depends(current_admin), db: AsyncSession = Depends(get_db)) -> AdminOut:
    service.require_frontend_origin(request)
    user = principal.user
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=400, detail="Choose a different password")
    user.password_hash = hash_password(data.new_password)
    user.must_change_password = False
    await service.revoke_sessions(db, user.id)
    service.log(db, "password_changed", user.id, user.id)
    await service.create_session(db, user, response)
    response.headers["Cache-Control"] = "no-store"
    return AdminOut.model_validate(user)


@auth_router.post("/logout", status_code=204)
async def logout(request: Request, response: Response, principal: Principal = Depends(current_admin),
                 db: AsyncSession = Depends(get_db)) -> None:
    service.require_frontend_origin(request)
    principal.session.revoked_at = service.now_utc()
    service.log(db, "logout", principal.user.id, principal.user.id)
    await db.commit()
    service.clear_cookie(response)


@router.get("/admins")
async def list_admins(_: Principal = Depends(super_admin), db: AsyncSession = Depends(get_db)) -> list[dict]:
    users = (await db.execute(select(User).where(User.role.in_(("admin", "super_admin"))).order_by(User.id))).scalars().all()
    now = service.now_utc()
    rows = []
    for user in users:
        last_seen = (await db.execute(select(func.max(AdminSession.last_seen_at)).where(AdminSession.user_id == user.id))).scalar_one()
        online = (await db.execute(select(AdminSession.id).where(
            AdminSession.user_id == user.id, AdminSession.revoked_at.is_(None),
            AdminSession.expires_at > now, AdminSession.last_seen_at > now - timedelta(minutes=5),
        ).limit(1))).scalar_one_or_none() is not None
        rows.append({**AdminOut.model_validate(user).model_dump(), "last_seen_at": last_seen, "online": online})
    return rows


@router.post("/admins", response_model=TempPasswordOut, status_code=201)
async def create_admin(data: CreateAdminIn, request: Request, response: Response,
                       principal: Principal = Depends(super_admin), db: AsyncSession = Depends(get_db)) -> TempPasswordOut:
    service.require_frontend_origin(request)
    response.headers["Cache-Control"] = "no-store"
    if (await db.execute(select(User.id).where(User.email == data.email))).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Login ID already exists")
    password = service.temporary_password()
    user = User(full_name=data.full_name, email=data.email, password_hash=hash_password(password),
                role="admin", must_change_password=True)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Login ID already exists") from exc
    service.log(db, "admin_created", principal.user.id, user.id)
    await db.commit()
    await db.refresh(user)
    return TempPasswordOut(admin=AdminOut.model_validate(user), temporary_password=password)


@router.patch("/admins/{admin_id}/status", response_model=AdminOut)
async def set_admin_status(admin_id: int, data: SetStatusIn, request: Request,
                           principal: Principal = Depends(super_admin), db: AsyncSession = Depends(get_db)) -> AdminOut:
    service.require_frontend_origin(request)
    target = await db.get(User, admin_id)
    if target is None or target.role != "admin":
        raise HTTPException(status_code=404, detail="Regular admin not found")
    if target.is_active != data.is_active:
        target.is_active = data.is_active
        if not data.is_active:
            await service.revoke_sessions(db, target.id)
        service.log(db, "admin_enabled" if data.is_active else "admin_disabled", principal.user.id, target.id)
        await db.commit()
    return AdminOut.model_validate(target)


@router.post("/admins/{admin_id}/reset-password", response_model=TempPasswordOut)
async def reset_password(admin_id: int, request: Request, response: Response,
                         principal: Principal = Depends(super_admin), db: AsyncSession = Depends(get_db)) -> TempPasswordOut:
    service.require_frontend_origin(request)
    response.headers["Cache-Control"] = "no-store"
    target = await db.get(User, admin_id)
    if target is None or target.role != "admin":
        raise HTTPException(status_code=404, detail="Regular admin not found")
    password = service.temporary_password()
    target.password_hash = hash_password(password)
    target.must_change_password = True
    await service.revoke_sessions(db, target.id)
    service.log(db, "password_reset", principal.user.id, target.id)
    await db.commit()
    return TempPasswordOut(admin=AdminOut.model_validate(target), temporary_password=password)


@router.get("/audit")
async def audit(_: Principal = Depends(super_admin), db: AsyncSession = Depends(get_db),
                actor_id: int | None = None, action: str | None = None,
                limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)) -> dict:
    query = select(AdminAuditLog)
    if actor_id is not None:
        query = query.where(AdminAuditLog.actor_user_id == actor_id)
    if action:
        query = query.where(AdminAuditLog.action == action)
    total = (await db.execute(select(func.count()).select_from(query.subquery()))).scalar_one()
    entries = (await db.execute(query.order_by(AdminAuditLog.id.desc()).offset(offset).limit(limit))).scalars().all()
    return {"total": total, "items": [{
        "id": entry.id, "actor_user_id": entry.actor_user_id, "target_user_id": entry.target_user_id,
        "action": entry.action, "detail": entry.detail, "created_at": entry.created_at,
    } for entry in entries]}
