"""Helpers for turning reference-like seed code into student-facing starters."""

import re

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
