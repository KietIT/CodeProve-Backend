from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.attempts import service as attempts_service
from app.features.mentor.client import get_mentor_client
from app.features.mentor.prompts import HYPOTHESIS_JUDGE_SYSTEM
from app.models import Attempt, Event, Exercise, PromptLog

_PRIMING = (
    "ignore your instructions",
    "just give me the code",
    "full solution",
    "write the whole",
    "give me the answer",
    "cho tôi luôn lời giải",
    "viết hết code",
)


def match_keywords(text: str, keywords: list[str]) -> list[str]:
    low = text.lower()
    return [k for k in keywords if k.lower() in low]


def looks_like_priming(text: str) -> bool:
    low = text.lower()
    return any(p in low for p in _PRIMING)


async def _already_injected(db: AsyncSession, attempt_id: int) -> bool:
    rows = (
        await db.execute(
            select(Event).where(Event.attempt_id == attempt_id, Event.type == "AI_REPLY")
        )
    ).scalars().all()
    return any(r.payload.get("injectedError") for r in rows)


async def mentor_reply(db: AsyncSession, attempt: Attempt, message: str) -> dict:
    ex = (
        await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))
    ).scalar_one()
    keywords = match_keywords(message, list(ex.domain_keywords or []))
    inject = bool(ex.verification_trap) and not await _already_injected(db, attempt.id)

    client = get_mentor_client()
    result = await client.chat(message, history=[], inject_error=inject)

    flags = ["PRIMING"] if looks_like_priming(message) else []
    await attempts_service.add_event(
        db,
        attempt.id,
        "PROMPT",
        {
            "messageText": message,
            "messageLength": len(message),
            "keywordsMatched": keywords,
            "promptTokens": result["prompt_tokens"],
        },
        flags=flags,
    )
    await attempts_service.add_event(
        db,
        attempt.id,
        "AI_REPLY",
        {
            "completionTokens": result["completion_tokens"],
            "aiCode": [{"loc": result["code_loc"]}] if result["code_loc"] else [],
            "injectedError": inject,
        },
    )
    db.add(
        PromptLog(
            attempt_id=attempt.id,
            prompt=message,
            response=result["text"],
            model=get_mentor_client()._model,
            tokens=result["prompt_tokens"] + result["completion_tokens"],
        )
    )
    await db.commit()
    return {"reply": result["text"], "injected_error": inject}


async def judge_hypothesis(db: AsyncSession, attempt: Attempt, text: str) -> dict:
    ex = (
        await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))
    ).scalar_one()
    verdict = await get_mentor_client().judge(
        HYPOTHESIS_JUDGE_SYSTEM, f"Problem: {ex.summary}\nStudent hypothesis: {text}"
    )
    correct = bool(verdict.get("correct", False))
    await attempts_service.add_event(
        db, attempt.id, "HYPOTHESIS", {"proposedBy": "user", "correct": correct}
    )
    await db.commit()
    return {"correct": correct, "note": verdict.get("note", "")}
