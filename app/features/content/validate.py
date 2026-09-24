"""Prove an exercise content file in the sandbox before it can be synced."""
from app.features.content.schema import ExerciseContent
from app.features.sandbox.runner import run_tests

VISIBLE_RANGE = (1, 2)
HIDDEN_MAX = 8
HIDDEN_MIN_DEFAULT = 5
MUTANT_RANGE = (3, 5)
REQUIRED_HIDDEN_CATEGORIES = ("boundary", "edge")


def _cases(content: ExerciseContent) -> list[dict]:
    return [{"input_data": t.input, "expected_output": t.expected, "description": t.description, "weight": 1.0}
            for t in content.tests]


def _changed_lines(reference: str, mutant: str) -> list[int] | None:
    a, b = reference.split("\n"), mutant.split("\n")
    if len(a) != len(b):
        return None
    return [i for i, (x, y) in enumerate(zip(a, b), start=1) if x != y]


def _structure_errors(content: ExerciseContent) -> list[str]:
    errors: list[str] = []
    visible = [t for t in content.tests if not t.hidden]
    hidden = [t for t in content.tests if t.hidden]
    hidden_min = content.limits.min_hidden if content.limits else HIDDEN_MIN_DEFAULT
    if not VISIBLE_RANGE[0] <= len(visible) <= VISIBLE_RANGE[1]:
        errors.append(f"visible tests: {len(visible)} (need {VISIBLE_RANGE[0]}-{VISIBLE_RANGE[1]})")
    if not hidden_min <= len(hidden) <= HIDDEN_MAX:
        errors.append(f"hidden tests: {len(hidden)} (need {hidden_min}-{HIDDEN_MAX})")
    for category in REQUIRED_HIDDEN_CATEGORIES:
        if not any(t.category == category for t in hidden):
            errors.append(f"no hidden '{category}' test")
    seen: set[str] = set()
    for t in content.tests:
        if t.description in seen:
            errors.append(f"duplicate test description: {t.description!r}")
        seen.add(t.description)
    if not MUTANT_RANGE[0] <= len(content.mutants) <= MUTANT_RANGE[1]:
        errors.append(f"mutants: {len(content.mutants)} (need {MUTANT_RANGE[0]}-{MUTANT_RANGE[1]})")
    return errors


async def validate_content(content: ExerciseContent, kind: str, starter_code: str, timeout: int = 5) -> list[str]:
    """Return every problem found (empty list = valid).

    kind / starter_code come from the exercise row (or the seed): a debug
    exercise's buggy starter must fail at least one test.
    """
    errors = _structure_errors(content)
    cases = _cases(content)

    ref = await run_tests(content.reference_solution, cases, timeout)
    if ref["runtime_error"]:
        errors.append(f"reference solution raises: {ref['runtime_error']}")
    failing = [c["name"] for c in ref["cases"] if not c["passed"]]
    if failing:
        errors.append(f"reference solution fails: {failing}")

    for i, mutant in enumerate(content.mutants, start=1):
        changed = _changed_lines(content.reference_solution, mutant.code)
        if changed is None:
            errors.append(f"mutant {i}: must keep the reference's number of lines")
        elif changed != [mutant.bug_line]:
            errors.append(f"mutant {i}: must change exactly line {mutant.bug_line}, changed {changed}")
        res = await run_tests(mutant.code, cases, timeout)
        if res["passed"] == res["total"]:
            errors.append(f"mutant {i}: no test kills it (equivalent mutant or missing test)")
        elif res["passed"] == 0:
            errors.append(f"mutant {i}: fails every test (too obviously broken to be a useful bug)")

    if kind == "debug":
        res = await run_tests(starter_code, cases, timeout)
        if res["passed"] == res["total"]:
            errors.append("debug starter passes every test: no test covers the planted bug")
    return errors
