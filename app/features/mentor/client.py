import json
import re

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.features.mentor.prompts import MENTOR_INJECT_SUFFIX, MENTOR_SYSTEM

_CODE_BLOCK = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


class MentorClient:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    async def chat(self, user_message: str, history: list[dict], inject_error: bool) -> dict:
        system = MENTOR_SYSTEM + (MENTOR_INJECT_SUFFIX if inject_error else "")
        messages = [{"role": "system", "content": system}, *history, {"role": "user", "content": user_message}]
        resp = await self._client.chat.completions.create(
            model=self._model, messages=messages, temperature=0.4, max_tokens=400
        )
        text = resp.choices[0].message.content or ""
        usage = resp.usage
        return {
            "text": text,
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "code_loc": _code_loc(text),
        }

    async def judge(self, system: str, user: str) -> dict:
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=300,
            response_format={"type": "json_object"},
        )
        try:
            return json.loads(resp.choices[0].message.content or "{}")
        except json.JSONDecodeError:
            return {}


def _code_loc(text: str) -> int:
    return sum(len(b.strip().splitlines()) for b in _CODE_BLOCK.findall(text))


_singleton: MentorClient | None = None


def get_mentor_client() -> MentorClient:
    global _singleton
    if _singleton is None:
        _singleton = MentorClient()
    return _singleton
