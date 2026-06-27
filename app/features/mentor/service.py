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


def build_exercise_context(ex: Exercise, student_code: str | None) -> str:
    """Compose the per-attempt context block injected into Ciel's system prompt
    so it can answer questions about *this* exercise instead of asking which one."""
    parts = [
        "CURRENT EXERCISE CONTEXT — the student is working on the exercise below.",
        "When they say \"this exercise\" / \"bài này\" / \"bài tập này\", they mean THIS one;",
        "explain it directly using the details here, but still NEVER write the full solution.",
        f"- Title: {ex.title}",
        f"- Difficulty / Level: {ex.difficulty} / {ex.level}",
        f"- Language: {ex.language}",
    ]
    if ex.summary:
        parts.append(f"- Summary: {ex.summary}")
    if ex.description:
        parts.append(f"- Description: {ex.description}")
    if ex.learning_objective:
        parts.append(f"- Learning objective: {ex.learning_objective}")
    if student_code and student_code.strip():
        parts.append(f"\nStudent's current code:\n```{ex.language}\n{student_code.strip()}\n```")
    return "\n".join(parts)


async def mentor_reply(
    db: AsyncSession, attempt: Attempt, message: str, code: str | None = None
) -> dict:
    ex = (
        await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))
    ).scalar_one()
    keywords = match_keywords(message, list(ex.domain_keywords or []))
    inject = bool(ex.verification_trap) and not await _already_injected(db, attempt.id)

    context = build_exercise_context(ex, code)
    client = get_mentor_client()
    result = await client.chat(message, history=[], inject_error=inject, context=context)

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
