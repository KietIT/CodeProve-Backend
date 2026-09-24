import pytest

from app.features.content.schema import ExerciseContent
from app.features.content.validate import validate_content

pytestmark = pytest.mark.asyncio

REF = ["def sum_to_n(n):", "    total = 0", "    for i in range(1, n + 1):", "        total += i", "    return total"]
BUGGY_STARTER = "def sum_to_n(n):\n    total = 0\n    for i in range(1, n):\n        total += i\n    return total"


def _t(desc, inp, exp, cat, hidden):
    return {"description": desc, "input": inp, "expected": exp, "category": cat, "hidden": hidden}


def _mut(line, new, bug_type="off-by-one"):
    code = list(REF)
    code[line - 1] = new
    return {"code": code, "bug_line": line, "bug_type": bug_type, "note_vi": "x", "note_en": "x"}


def _content(**over):
    raw = {
        "code": "CP-004",
        "reference_solution": REF,
        "tests": [
            _t("n=3", "sum_to_n(3)", "6", "happy", False),
            _t("n=5", "sum_to_n(5)", "15", "happy", False),
            _t("zero", "sum_to_n(0)", "0", "boundary", True),
            _t("one", "sum_to_n(1)", "1", "boundary", True),
            _t("negative", "sum_to_n(-4)", "0", "edge", True),
            _t("hundred", "sum_to_n(100)", "5050", "happy", True),
            _t("two", "sum_to_n(2)", "3", "happy", True),
        ],
        "mutants": [
            _mut(3, "    for i in range(1, n):"),
            _mut(4, "        total += i * i", "wrong-operator"),
            _mut(3, "    for i in range(2, n + 1):"),
        ],
        "review": {"status": "draft", "author": "claude", "reviewer": None},
    }
    raw.update(over)
    return ExerciseContent.model_validate(raw)


async def test_valid_content_has_no_errors():
    assert await validate_content(_content(), "debug", BUGGY_STARTER) == []


async def test_reference_must_pass_every_test():
    bad = list(REF); bad[4] = "    return total + 1"
    errors = await validate_content(_content(reference_solution=bad), "implement", "")
    assert any("reference solution fails" in e for e in errors)


async def test_equivalent_mutant_is_rejected():
    c = _content(mutants=[_mut(3, "    for i in range(0, n + 1):"), _mut(3, "    for i in range(1, n):"),
                          _mut(4, "        total += i * i")])
    errors = await validate_content(c, "implement", "")
    assert any("mutant 1: no test kills it" in e for e in errors)


async def test_mutant_must_change_exactly_its_bug_line():
    m = _mut(3, "    for i in range(1, n):")
    m["code"][1] = "    total = 1"
    errors = await validate_content(_content(mutants=[m, _mut(4, "        total += i * i"),
                                                      _mut(3, "    for i in range(2, n + 1):")]), "implement", "")
    assert any("mutant 1: must change exactly line 3" in e for e in errors)


async def test_mutant_failing_everything_is_not_plausible():
    c = _content(mutants=[_mut(5, "    return None"), _mut(3, "    for i in range(1, n):"),
                          _mut(4, "        total += i * i")])
    errors = await validate_content(c, "implement", "")
    assert any("mutant 1: fails every test" in e for e in errors)


async def test_hidden_test_count_and_categories():
    few = _content(tests=[_t("n=3", "sum_to_n(3)", "6", "happy", False),
                          _t("zero", "sum_to_n(0)", "0", "boundary", True),
                          _t("one", "sum_to_n(1)", "1", "boundary", True),
                          _t("two", "sum_to_n(2)", "3", "happy", True)])
    errors = await validate_content(few, "implement", "")
    assert any("hidden tests: 3" in e for e in errors)
    assert any("no hidden 'edge' test" in e for e in errors)


async def test_limits_lower_the_hidden_minimum():
    few = _content(tests=[_t("n=3", "sum_to_n(3)", "6", "happy", False),
                          _t("zero", "sum_to_n(0)", "0", "boundary", True),
                          _t("neg", "sum_to_n(-1)", "0", "edge", True),
                          _t("two", "sum_to_n(2)", "3", "happy", True)],
                   limits={"min_hidden": 3, "reason": "illustrating the override"})
    errors = await validate_content(few, "implement", "")
    assert not any("hidden tests" in e for e in errors)


async def test_debug_starter_must_fail_a_test():
    errors = await validate_content(_content(), "debug", "\n".join(REF))
    assert any("debug starter passes every test" in e for e in errors)


async def test_descriptions_must_be_unique():
    c = _content()
    c.tests[1].description = c.tests[0].description
    errors = await validate_content(c, "implement", "")
    assert any("duplicate test description" in e for e in errors)
