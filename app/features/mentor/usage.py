"""Log the token usage of every LLM call (P3.6).

The mentor client is one shared instance, so the request it serves comes from
a context variable: code that calls the LLM wraps the work in
`llm_scope(db, user_id, attempt_id)`, and the client adds an LlmCall row to
that session after each call; the caller's own commit stores it. Outside a
scope nothing is logged. Logging never breaks the call.
"""
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.features.mentor.prompts import (
    DAILY_CHALLENGE_SYSTEM, EXPLAIN_QUESTION_SYSTEM, EXPLAIN_SCORE_SYSTEM, FEEDBACK_WRITER_SYSTEM,
    HYPOTHESIS_JUDGE_SYSTEM, LOCATE_JUDGE_SYSTEM, PROMPT_JUDGE_SYSTEM,
)
from app.models import LlmCall

logger = logging.getLogger(__name__)

# A judge call's kind, from the system prompt it starts with.
_JUDGE_KINDS = (
    (EXPLAIN_QUESTION_SYSTEM, "explain_questions"), (EXPLAIN_SCORE_SYSTEM, "explain"),
    (HYPOTHESIS_JUDGE_SYSTEM, "hypothesis"), (LOCATE_JUDGE_SYSTEM, "locate"), (PROMPT_JUDGE_SYSTEM, "prompts"),
    (DAILY_CHALLENGE_SYSTEM, "daily"), (FEEDBACK_WRITER_SYSTEM, "feedback"),
)


@dataclass(frozen=True)
class _Scope:
    db: AsyncSession
    user_id: int | None
    attempt_id: int | None
    names: tuple[str, ...] = ()  # the student's full name, scrubbed from what is sent (P3.7)


_scope: ContextVar[_Scope | None] = ContextVar("llm_scope", default=None)


@contextmanager
def llm_scope(db: AsyncSession, user_id: int | None = None, attempt_id: int | None = None,
              names: tuple[str, ...] = ()) -> Iterator[None]:
    token = _scope.set(_Scope(db, user_id, attempt_id, names))
    try:
        yield
    finally:
        _scope.reset(token)


def scope_names() -> tuple[str, ...]:
    scope = _scope.get()
    return scope.names if scope else ()


def judge_kind(system: str) -> str:
    return next((kind for prompt, kind in _JUDGE_KINDS if system.startswith(prompt)), "other")


def record(kind: str, model: str, prompt_tokens: int, cached_tokens: int, completion_tokens: int) -> None:
    scope = _scope.get()
    if scope is None:
        return
    try:
        scope.db.add(LlmCall(kind=kind, model=model, prompt_tokens=prompt_tokens, cached_tokens=cached_tokens,
                             completion_tokens=completion_tokens, user_id=scope.user_id,
                             attempt_id=scope.attempt_id))
    except Exception:
        logger.exception("could not log an LLM call (%s)", kind)
