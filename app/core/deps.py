from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import decode_token
from app.models import User

_bearer = HTTPBearer(auto_error=False)
# RFC 6750: 401 responses for Bearer auth must carry this header.
_UNAUTH_HEADERS = {"WWW-Authenticate": "Bearer"}


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated", headers=_UNAUTH_HEADERS
        )
    sub = decode_token(creds.credentials)
    if sub is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token", headers=_UNAUTH_HEADERS
        )
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        # A token whose subject is not an integer is invalid, not a server error.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token", headers=_UNAUTH_HEADERS
        )
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found", headers=_UNAUTH_HEADERS
        )
    return user


async def get_current_user_optional(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Same identity resolution as get_current_user, but returns None instead
    of raising 401 - for endpoints that must work for anonymous visitors too
    (Daily Bug Hunt, spec section 7)."""
    if creds is None:
        return None
    sub = decode_token(creds.credentials)
    if sub is None:
        return None
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        return None
    return (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
