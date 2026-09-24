"""Helpers for turning reference-like seed code into student-facing starters."""

import io
import re
import tokenize

_DEF_RE = re.compile(r"^(?P<indent>\s*)def\s+.+:\s*$")
_CLASS_RE = re.compile(r"^(?P<indent>\s*)class\s+.+:\s*$")
_KEEP_TOP_LEVEL_RE = re.compile(
    r"^[A-Za-z_]\w*\s*=\s*(\{\}|\[\]|0|None|False|True)$"
)


def student_safe_starter(source: str) -> str:
    """Keep signatures/imports, strip implementation bodies.

    Several MVP seed entries used working reference code as starter code. The
    assessment UI should show a scaffold, not a ready-to-submit solution.
    """
    lines = source.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    skip_body_indent: int | None = None
    saw_callable = False

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if skip_body_indent is not None:
            if stripped and indent > skip_body_indent:
                continue
            skip_body_indent = None

        if not stripped:
            if out and out[-1] != "":
                out.append("")
            continue

        if stripped.startswith(("import ", "from ")):
            out.append(line)
            continue

        if indent == 0 and _KEEP_TOP_LEVEL_RE.match(stripped):
            out.append(line)
            continue

        class_match = _CLASS_RE.match(line)
        if class_match:
            out.append(line)
            out.append(f"{class_match.group('indent')}    pass")
            saw_callable = True
            continue

        def_match = _DEF_RE.match(line)
        if def_match:
            out.append(line)
            out.append(f"{def_match.group('indent')}    pass")
            skip_body_indent = indent
            saw_callable = True

    if not saw_callable:
        return source
    return "\n".join(out).strip()


def strip_comments(source: str) -> str:
    """Remove `#` comments so a starter cannot leak the bug it contains.

    Uses the tokenizer, so a '#' inside a string literal is kept. A line that
    held only a comment is dropped. Source that cannot be tokenized is
    returned unchanged rather than half-stripped.
    """
    source = source.replace("\r\n", "\n")
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return source
    comment_col = {t.start[0]: t.start[1] for t in tokens if t.type == tokenize.COMMENT}
    if not comment_col:
        return source
    out: list[str] = []
    for lineno, line in enumerate(source.split("\n"), start=1):
        col = comment_col.get(lineno)
        if col is None:
            out.append(line)
            continue
        kept = line[:col].rstrip()
        if kept:
            out.append(kept)
    return "\n".join(out)


def student_starter(starter_code: str, kind: str) -> str:
    """The starter exactly as the student sees it in the editor."""
    return strip_comments(starter_code) if kind == "debug" else student_safe_starter(starter_code)


def normalize_code(source: str) -> str:
    lines = (line.rstrip() for line in source.replace("\r\n", "\n").split("\n"))
    return "\n".join(line for line in lines if line)


def is_untouched(source: str, starter: str) -> bool:
    """True for an empty editor or the unmodified starter (whitespace-insensitive)."""
    code = normalize_code(source)
    return code == "" or code == normalize_code(starter)
