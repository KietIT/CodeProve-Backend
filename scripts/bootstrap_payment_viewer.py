"""Run after migrations: python -m scripts.bootstrap_payment_viewer.

The password is prompted without echo, or read from PAYMENT_VIEWER_PASSWORD.
Existing accounts are never promoted, re-enabled or reset by this command.
"""
import asyncio
from getpass import getpass
import os

from sqlalchemy import select

from app.core.db import async_session_maker
from app.core.security import hash_password
from app.features.admin.service import log
from app.models import User

EMAIL = "lecture@codeprove.vn"


async def bootstrap(password: str) -> bool:
    if len(password) < 8 or len(password.encode("utf-8")) > 72:
        raise ValueError("Password must be at least 8 characters and at most 72 UTF-8 bytes")
    async with async_session_maker() as db:
        existing = (await db.execute(select(User).where(User.email == EMAIL))).scalar_one_or_none()
        if existing is not None:
            if existing.role != "payment_viewer":
                raise RuntimeError(f"Conflicting account: {EMAIL}; no changes made")
            return False
        user = User(full_name="Lecturer", email=EMAIL, role="payment_viewer",
                    password_hash=hash_password(password), must_change_password=False)
        db.add(user)
        await db.flush()
        log(db, "payment_viewer_bootstrapped", None, user.id)
        await db.commit()
        return True


if __name__ == "__main__":
    password = os.environ.get("PAYMENT_VIEWER_PASSWORD") or getpass("Lecturer password: ")
    created = asyncio.run(bootstrap(password))
    print(f"{EMAIL}: created" if created else f"{EMAIL}: already exists; unchanged")
