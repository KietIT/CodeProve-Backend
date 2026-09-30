"""Where the bug is in a debug exercise (P2.2).

A debug exercise's reference solution is its starter with the bug fixed, so
the lines the fix touches are the bug. Line numbers are those of the starter
the student sees (`student_starter`: comments stripped, comment-only lines
dropped), because that is what they click on.
"""
import difflib

from app.features.exercises.starters import strip_comments


def derive(served_starter: str, reference: str) -> list[list[int]]:
    """1-based line groups of the served starter that the fix replaces or deletes.
    Pure insertions (a new import, a new lock) have no line to click, so they
    only count when nothing else changed: then the line right after them."""
    served = served_starter.replace("\r\n", "\n").split("\n")
    fixed = strip_comments(reference).split("\n")
    ops = difflib.SequenceMatcher(a=served, b=fixed, autojunk=False).get_opcodes()
    regions = [list(range(i1 + 1, i2 + 1)) for tag, i1, i2, _, _ in ops if tag in ("replace", "delete")]
    if regions:
        return regions
    return [[min(i1 + 1, len(served))] for tag, i1, _, _, _ in ops if tag == "insert"]


def hint_range(regions: list[list[int]], line_count: int) -> tuple[int, int]:
    """The second hint: every region widened by one line each side, as one range."""
    lines = [line for region in regions for line in region]
    return max(1, min(lines) - 1), min(line_count, max(lines) + 1)


def hit_regions(regions: list[list[int]], selected: list[int]) -> list[bool]:
    chosen = set(selected)
    return [bool(chosen & set(region)) for region in regions]
