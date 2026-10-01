"""Which language Ciel replies in, decided per message (fix 2026-10-01).

The system prompt says "answer in the user's language", but with the attempt's
history (P3.1) in one language the model keeps it even when the student
switches. So the server detects the language of the latest message and states
it in this turn's instructions, after the history.
"""
import re

_CODE = re.compile(r"```.*?(```|$)|`[^`]*`", re.DOTALL)
_VI_LETTERS = set("àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ")
# Common Vietnamese words typed without accents; none is a common English word.
_VI_PLAIN = {"toi", "giup", "khong", "bai", "lam", "sao", "nay", "cho", "minh", "duoc", "nhu", "nao", "cua",
             "voi", "roi", "hieu", "viet", "dung", "chua", "gium", "dum", "nhe", "nha", "oi", "tai", "thi",
             "ham", "loi", "sai", "chay", "giai", "thich", "cach", "phai", "gi", "vay"}
_TOO_SHORT = {"ok", "oke", "okay", "ty", "yes", "no", "hi"}

RULES = {
    "vi": "LANGUAGE: the student's latest message is in Vietnamese. Reply in Vietnamese, whatever language "
          "earlier messages in this conversation used.",
    "en": "LANGUAGE: the student's latest message is in English. Reply in English, whatever language earlier "
          "messages in this conversation used.",
}


def detect(text: str) -> str | None:
    """'vi', 'en', or None when the message says too little (code only, "ok", numbers)."""
    prose = _CODE.sub(" ", text or "").lower()
    if any(ch in _VI_LETTERS for ch in prose):
        return "vi"
    words = re.findall(r"[a-z]+", prose)
    if len({w for w in words if w in _VI_PLAIN}) >= 2:
        return "vi"
    if not words or (len(words) == 1 and words[0] in _TOO_SHORT):
        return None
    return "en"


def reply_language(message: str, previous_prompts: list[str]) -> str | None:
    """The latest message's language, else that of the most recent earlier message that has one."""
    for text in [message, *reversed(previous_prompts)]:
        language = detect(text)
        if language:
            return language
    return None
