from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models import User
from app.schemas.auth import LoginIn, SignupIn, UpdateMeIn


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
