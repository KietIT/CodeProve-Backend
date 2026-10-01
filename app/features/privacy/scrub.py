"""Remove personal data from student text before it leaves for an LLM (P3.7).

Emails, Vietnamese phone numbers and the student's own full name (whole, any
case, at least two words: a single given name could also be a word in code).
Approved 2026-10-01 without a student-ID pattern: students come from many
schools with different ID formats. What we store is left as typed.
"""
import re
from collections.abc import Iterable

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+84|0)\d{9,10}(?!\d)")


def _name_pattern(name: str) -> re.Pattern[str] | None:
    words = name.split()
    if len(words) < 2:
        return None
    return re.compile(r"(?<!\w)" + r"\s+".join(map(re.escape, words)) + r"(?!\w)", re.IGNORECASE)


def scrub(text: str | None, names: Iterable[str] = ()) -> str:
    if not text:
        return ""
    out = _PHONE.sub("[số điện thoại]", _EMAIL.sub("[email]", text))
    for name in names:
        pattern = _name_pattern(name or "")
        if pattern:
            out = pattern.sub("[tên]", out)
    return out
