"""Create the four initial admin accounts after `alembic upgrade head`.

Run interactively: `python -m scripts.bootstrap_admins`. Newly generated
temporary passwords appear once on stdout. Deliver each one privately.
Existing admin accounts are left untouched; a conflicting learner ID aborts.
"""
import asyncio

from sqlalchemy import select

from app.core.db import async_session_maker
from app.core.security import hash_password
from app.features.admin.service import log, temporary_password
from app.models import User

INITIAL_ADMINS = (
    ("Trung", "trung@codeprove.production", "super_admin"),
    ("Kiet", "kiet@codeprove.production", "admin"),
    ("Phat", "phat@codeprove.production", "admin"),
    ("Minh", "minh@codeprove.production", "admin"),
)


async def bootstrap() -> None:
    async with async_session_maker() as db:
        existing = (await db.execute(select(User).where(
            User.email.in_([email for _, email, _ in INITIAL_ADMINS])
        ))).scalars().all()
        by_email = {user.email: user for user in existing}
        for _, email, role in INITIAL_ADMINS:
            user = by_email.get(email)
            if user is not None and user.role != role:
                raise RuntimeError(f"Conflicting existing account: {email}; no accounts created")

        created: list[tuple[str, str]] = []
        for name, email, role in INITIAL_ADMINS:
            if email in by_email:
                continue
            password = temporary_password()
            user = User(full_name=name, email=email, role=role,
                        password_hash=hash_password(password), must_change_password=True)
            db.add(user)
            await db.flush()
            log(db, "admin_bootstrapped", None, user.id)
            created.append((email, password))
        await db.commit()

    if not created:
        print("All four admin accounts already exist; no passwords were changed.")
    else:
        print("Temporary credentials (shown once; deliver privately):")
        for email, password in created:
            print(f"{email}: {password}")


if __name__ == "__main__":
    asyncio.run(bootstrap())
