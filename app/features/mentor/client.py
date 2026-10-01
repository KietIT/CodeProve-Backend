import json

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.features.mentor import usage as llm_usage
from app.features.mentor.guard import LOCATE_RETRY_INSTRUCTION, RETRY_INSTRUCTION, code_blocks
from app.features.mentor.prompts import MENTOR_INJECT_SUFFIX, MENTOR_SYSTEM


def chat_messages(user_message: str, history: list[dict], inject_error: bool, context: str = "",
                  extra_instruction: str = "") -> list[dict]:
    """Ciel's messages, laid out for OpenAI's automatic prompt caching (P3.6).

    Caching reuses the longest common prefix of consecutive requests, so what
    stays the same through an attempt comes first (rules + exercise + learner
    brief + hint style, then the growing history) and what changes per turn
    comes last: this turn's instructions (trap, locate rule, guard retry) in a
    second system message, then the question with the student's current code.
    """
    turn = "\n\n".join(part for part in (MENTOR_INJECT_SUFFIX.strip() if inject_error else "", extra_instruction)
                       if part)
    static = f"{MENTOR_SYSTEM}\n\n{context}" if context else MENTOR_SYSTEM
    return [
        {"role": "system", "content": static},
        *history,
        *([{"role": "system", "content": turn}] if turn else []),
        {"role": "user", "content": user_message},
    ]


def _tokens(resp) -> tuple[int, int, int]:
    """(prompt, cached, completion) tokens of a completion; zeros when the API gave no usage."""
    usage = resp.usage
    if not usage:
        return 0, 0, 0
    details = getattr(usage, "prompt_tokens_details", None)
    cached = (getattr(details, "cached_tokens", 0) or 0) if details else 0
    return usage.prompt_tokens, cached, usage.completion_tokens


class MentorClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def chat(
        self,
        user_message: str,
        history: list[dict],
        inject_error: bool,
        context: str = "",
        extra_instruction: str = "",
    ) -> dict:
        messages = chat_messages(user_message, history, inject_error, context, extra_instruction)
        resp = await self._client.chat.completions.create(
            model=self._model, messages=messages, temperature=0.4, max_tokens=400
        )
        text = resp.choices[0].message.content or ""
        prompt_tokens, cached_tokens, completion_tokens = _tokens(resp)
        retry = RETRY_INSTRUCTION in extra_instruction or LOCATE_RETRY_INSTRUCTION in extra_instruction
        llm_usage.record("ciel_retry" if retry else "ciel", self._model, prompt_tokens, cached_tokens,
                         completion_tokens)
        return {
            "text": text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "code_loc": code_loc(text),
        }

    async def judge(self, system: str, user: str, max_tokens: int = 300) -> dict:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        llm_usage.record(llm_usage.judge_kind(system), self._model, *_tokens(resp))
        try:
            return json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            return {}


def code_loc(text: str) -> int:
    return sum(len(b.strip().splitlines()) for b in code_blocks(text))


_singleton: MentorClient | None = None


def get_mentor_client() -> MentorClient:
    global _singleton
    if _singleton is None:
        _singleton = MentorClient()
    return _singleton
