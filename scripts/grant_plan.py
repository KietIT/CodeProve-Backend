"""Give a learner a plan without payment (testing, goodwill, or a refund decided by support).

    python -m scripts.grant_plan <email> plus|pro [days]     # default 30 days, starts now
    python -m scripts.grant_plan <email> free                # ends the plan now

Replaces whatever plan the account had. Prefer the admin tools once they exist; this is the operator's escape hatch.
"""
import asyncio
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.db import async_session_maker
from app.models import Subscription, User


async def main(email: str, tier: str, days: int) -> int:
    async with async_session_maker() as db:
        user = (await db.execute(select(User).where(User.email == email.lower(), User.role == "user"))).scalar_one_or_none()
        if user is None:
            print(f"No learner with email {email}")
            return 1
        sub = (await db.execute(select(Subscription).where(Subscription.user_id == user.id))).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if tier == "free":
            if sub is not None:
                sub.expires_at = now
            await db.commit()
            print(f"{email}: back to free")
            return 0
        expires = now + timedelta(days=days)
        if sub is None:
            db.add(Subscription(user_id=user.id, tier=tier, expires_at=expires))
        else:
            sub.tier, sub.expires_at = tier, expires
        await db.commit()
        print(f"{email}: {tier} until {expires:%Y-%m-%d %H:%M} UTC")
        return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) not in (2, 3) or args[1] not in ("free", "plus", "pro") or (len(args) == 3 and not args[2].isdigit()):
        print(__doc__)
        sys.exit(2)
    sys.exit(asyncio.run(main(args[0], args[1], int(args[2]) if len(args) == 3 else 30)))
