from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import rate_limit
from app.core.config import get_settings
from app.core.db import get_db
from app.core.deps import get_current_user
from app.features.sandbox import runner
from app.models import Exercise, TestCase, User
from app.schemas.practice import TraceIn

router = APIRouter(prefix="/api/practice", tags=["practice"])


async def _first_visible_input(db: AsyncSession, exercise_code: str) -> str:
    """Input expression of the exercise's first VISIBLE test case (falls back to
    the first case). Hidden inputs drive nothing here, so they aren't leaked."""
    ex = (
        await db.execute(select(Exercise).where(Exercise.code == exercise_code.upper()))
    ).scalar_one_or_none()
    if ex is None:
        return ""
    # is_hidden False (0) sorts first, then by order_index.
    tc = (
        await db.execute(
            select(TestCase)
            .where(TestCase.exercise_id == ex.id)
            .order_by(TestCase.is_hidden, TestCase.order_index)
        )
    ).scalars().first()
    return tc.input_data if tc and not tc.is_hidden else ""


@router.post("/trace")
async def trace(data: TraceIn, db: AsyncSession = Depends(get_db),
                user: User = Depends(get_current_user)) -> dict:
    """Trace the student's code step by step for the algorithm visualizer.
    Non-graded practice aid: runs in the same sandbox as /run, with a timeout.
    Executes arbitrary code, so it requires login and is rate limited."""
    settings = get_settings()
    rate_limit.enforce(f"sandbox:{user.id}", settings.sandbox_rate_limit_per_minute, 60)
    call = data.call or ""
    if not call and data.exercise_code:
        call = await _first_visible_input(db, data.exercise_code)
    return await runner.trace_code(data.source_code, call, settings.sandbox_timeout)
