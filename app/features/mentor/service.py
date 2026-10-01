import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.features.attempts import debug
from app.features.attempts import service as attempts_service
from app.features.learner.brief import learner_brief
from app.features.learner.profile import profile
from app.features.mentor import guard, language
from app.features.mentor.client import code_loc, get_mentor_client
from app.features.mentor.memory import attempt_history
from app.features.mentor.prompts import HINT_STYLE, LEARNER_BLOCK, SENIOR_CODE_ALLOWED
from app.features.scoring.judges import judge_hypothesis as judge_hypothesis_text
from app.models import Attempt, Event, Exercise, PromptLog, User

logger = logging.getLogger(__name__)

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


# Explicit requests for code (not a student talking about their own code).
_CODE_REQUESTS = (
    "show me code", "show me the code", "give me code", "give me the code", "write the code", "write code",
    "code example", "example code", "sample code", "cho xem code", "cho em code", "cho tôi code",
    "cho mình code", "cho em xem code", "viết code", "viết giúp", "viết hộ", "code mẫu", "code ví dụ",
    "ví dụ code", "đưa code",
)


def asks_for_code(text: str) -> bool:
    low = text.lower()
    return looks_like_priming(text) or any(p in low for p in _CODE_REQUESTS)


async def hint_style(db: AsyncSession, attempt: Attempt, ex: Exercise, message: str) -> str:
    """How concrete Ciel's help is, by exercise level (P3.5). On a senior exercise a small
    fragment becomes allowed once the student has asked for code twice in this attempt."""
    style = HINT_STYLE.get(ex.level, "")
    if ex.level != "senior":
        return style
    prompts = (await db.execute(select(PromptLog.prompt).where(PromptLog.attempt_id == attempt.id))).scalars().all()
    asked = sum(asks_for_code(p or "") for p in [*prompts, message])
    return f"{style}\n{SENIOR_CODE_ALLOWED}" if asked >= 2 else style


async def _already_injected(db: AsyncSession, attempt_id: int) -> bool:
    rows = (
        await db.execute(
            select(Event).where(Event.attempt_id == attempt_id, Event.type == "AI_REPLY")
        )
    ).scalars().all()
    return any(r.payload.get("injectedError") for r in rows)


def build_exercise_context(ex: Exercise) -> str:
    """Compose the per-attempt context block injected into Ciel's system prompt
    so it can answer questions about *this* exercise instead of asking which one.
    The student's code is not part of it: it changes every turn, so it goes with
    the question (with_code) to keep this prefix cacheable (P3.6)."""
    parts = [
        "CURRENT EXERCISE CONTEXT - the student is working on the exercise below.",
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
    return "\n".join(parts)


def with_code(message: str, code: str | None, language: str) -> str:
    """This turn's user message: the question, then the code currently in the editor."""
    if not code or not code.strip():
        return message
    return f"{message}\n\nMy current code:\n```{language}\n{code.strip()}\n```"


async def learner_context(db: AsyncSession, user_id: int) -> str:
    """The learner brief block for Ciel (P3.5), or "" for a student with no scored exercise or
    who turned AI personalisation off (P3.7). Optional: a failure is logged and Ciel answers without it."""
    try:
        personal = (await db.execute(select(User.ai_personalization).where(User.id == user_id))).scalar_one()
        if not personal:
            return ""
        p = await profile(db, user_id)
    except Exception:
        logger.exception("learner profile failed for user %s", user_id)
        return ""
    return f"{LEARNER_BLOCK}{learner_brief(p, 'en')}" if p.scored_attempts else ""


async def mentor_reply(
    db: AsyncSession, attempt: Attempt, message: str, code: str | None = None
) -> dict:
    ex = (
        await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))
    ).scalar_one()
    keywords = match_keywords(message, list(ex.domain_keywords or []))
    inject = bool(ex.verification_trap) and not await _already_injected(db, attempt.id)

    context = build_exercise_context(ex)
    learner = await learner_context(db, attempt.user_id)
    if learner:
        context = f"{context}\n\n{learner}"
    client = get_mentor_client()
    # Debug exercise whose bug the student has not located yet: Ciel may only help them find it.
    hidden_bug = await debug.hidden_bug(db, attempt, ex)
    locate_rule = guard.LOCATE_INSTRUCTION if hidden_bug else ""
    style = await hint_style(db, attempt, ex, message)
    earlier = (await db.execute(select(PromptLog.prompt).where(PromptLog.attempt_id == attempt.id)
                                .order_by(PromptLog.id))).scalars().all()
    reply_in = language.reply_language(message, [p or "" for p in earlier])
    # This turn's rules, after the history: the reply language first; the locate rule comes after the
    # hint style and overrides it.
    instruction = "\n\n".join(part for part in (language.RULES.get(reply_in or "", ""), style, locate_rule)
                              if part)

    async def problems(text: str) -> tuple[bool, bool]:
        solves = await guard.solves_exercise(db, ex.id, text)
        return solves, bool(hidden_bug) and guard.reveals_bug(text, *hidden_bug)

    history = await attempt_history(db, attempt.id)  # P3.1: the conversation of this attempt
    question = with_code(message, code, ex.language)
    result = await client.chat(question, history=history, inject_error=inject, context=context,
                               extra_instruction=instruction)
    prompt_tokens, completion_tokens = result["prompt_tokens"], result["completion_tokens"]
    cached_tokens = result.get("cached_tokens", 0)
    withheld, revealed = await problems(result["text"])
    if withheld or revealed:
        # Never shown, so the trap (if any) was not served either: ask again without it.
        inject = False
        stricter = "\n\n".join(part for part in (
            instruction, guard.RETRY_INSTRUCTION if withheld else "",
            guard.LOCATE_RETRY_INSTRUCTION if revealed else "") if part)
        retry = await client.chat(question, history=history, inject_error=False, context=context,
                                  extra_instruction=stricter)
        prompt_tokens += retry["prompt_tokens"]
        cached_tokens += retry.get("cached_tokens", 0)
        completion_tokens += retry["completion_tokens"]
        still_solves, still_reveals = await problems(retry["text"])
        text = guard.BUG_FALLBACK if still_reveals else guard.FALLBACK if still_solves else retry["text"]
        result = {**retry, "text": text, "code_loc": code_loc(text)}

    flags = ["PRIMING"] if looks_like_priming(message) else []
    await attempts_service.add_event(
        db,
        attempt.id,
        "PROMPT",
        {
            "messageText": message,
            "messageLength": len(message),
            "keywordsMatched": keywords,
            "promptTokens": prompt_tokens,
            "cachedTokens": cached_tokens,  # P3.6: prompt tokens served from OpenAI's cache
        },
        flags=flags,
    )
    await attempts_service.add_event(
        db,
        attempt.id,
        "AI_REPLY",
        {
            "completionTokens": completion_tokens,
            "aiCode": [{"loc": result["code_loc"]}] if result["code_loc"] else [],
            "injectedError": inject,
            "withheldSolution": withheld,
            "withheldBugLocation": revealed,
        },
    )
    # Only what the student saw is stored: the Verification axis and the raters read these replies.
    db.add(
        PromptLog(
            attempt_id=attempt.id,
            prompt=message,
            response=result["text"],
            model=get_mentor_client()._model,
            tokens=prompt_tokens + completion_tokens,
        )
    )
    await db.commit()
    return {"reply": result["text"]}


async def judge_hypothesis(db: AsyncSession, attempt: Attempt, text: str) -> dict:
    ex = (
        await db.execute(select(Exercise).where(Exercise.id == attempt.exercise_id))
    ).scalar_one()
    verdict = await judge_hypothesis_text(get_mentor_client(), ex.summary, text)
    # Keep the text itself (capped): human raters and the rubric read the
    # hypothesis, not just the verdict. `level` feeds rubric v2 (None = unrated).
    await attempts_service.add_event(
        db, attempt.id, "HYPOTHESIS",
        {"proposedBy": "user", "correct": verdict["correct"], "text": text[:2000], "note": verdict["note"],
         "level": verdict["level"], "levelEvidence": verdict["evidence"]},
    )
    await db.commit()
    return {"correct": verdict["correct"], "note": verdict["note"]}
