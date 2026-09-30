"""What Ciel remembers of the current attempt (P3.1).

The last MAX_EXCHANGES question/answer pairs of the same attempt, oldest first,
as chat history. Only what the student saw is used (`PromptLog`: a withheld
reply was already replaced there). Long messages are cut and the oldest pairs
dropped to stay within MAX_TOTAL_CHARS. Across attempts Ciel only gets the
learner brief (P3.3/P3.5), never raw chat.
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PromptLog

MAX_EXCHANGES = 6
MAX_MESSAGE_CHARS = 2000
MAX_TOTAL_CHARS = 8000


def _cap(text: str) -> str:
    return text if len(text) <= MAX_MESSAGE_CHARS else text[:MAX_MESSAGE_CHARS] + "…"


async def attempt_history(db: AsyncSession, attempt_id: int) -> list[dict]:
    rows = (await db.execute(select(PromptLog).where(PromptLog.attempt_id == attempt_id)
                             .order_by(PromptLog.id.desc()).limit(MAX_EXCHANGES))).scalars().all()
    history: list[dict] = []
    for row in reversed(rows):
        history += [{"role": "user", "content": _cap(row.prompt or "")},
                    {"role": "assistant", "content": _cap(row.response or "")}]
    while history and sum(len(m["content"]) for m in history) > MAX_TOTAL_CHARS:
        history = history[2:]  # drop the oldest exchange
    return history
