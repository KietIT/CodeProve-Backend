from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.privacy.service import POLICY_VERSION, has_consent, record_consent
from app.models import User
from app.schemas.privacy import ConsentIn, PrivacyOut, PrivacyUpdateIn

router = APIRouter(prefix="/api/me/privacy", tags=["privacy"])


def _out(user: User) -> PrivacyOut:
    return PrivacyOut(consented=has_consent(user), version=user.privacy_version, current_version=POLICY_VERSION,
                      ai_personalization=user.ai_personalization)


@router.get("", response_model=PrivacyOut)
async def get_privacy(user: User = Depends(get_current_user)) -> PrivacyOut:
    return _out(user)


@router.post("/consent", response_model=PrivacyOut)
async def consent(data: ConsentIn, db: AsyncSession = Depends(get_db),
                  user: User = Depends(get_current_user)) -> PrivacyOut:
    if data.version != POLICY_VERSION:
        # The page showed an older text: reload it before accepting.
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail={"code": "privacy_version_outdated", "current_version": POLICY_VERSION})
    record_consent(user)
    await db.commit()
    return _out(user)


@router.patch("", response_model=PrivacyOut)
async def update_privacy(data: PrivacyUpdateIn, db: AsyncSession = Depends(get_db),
                         user: User = Depends(get_current_user)) -> PrivacyOut:
    user.ai_personalization = data.ai_personalization
    await db.commit()
    return _out(user)
