import json

import pytest
from pydantic import ValidationError

from app.features.content.schema import ExerciseContent, load_content_file


def _raw(**over):
    raw = {
        "code": "CP-004",
        "reference_solution": ["def f(n):", "    return n + 1"],
        "tests": [{"description": "one", "input": "f(1)", "expected": "2", "category": "happy", "hidden": False}],
        "mutants": [{"code": ["def f(n):", "    return n - 1"], "bug_line": 2, "bug_type": "wrong-operator",
                     "note_vi": "Dấu trừ thay cho dấu cộng.", "note_en": "Minus instead of plus."}],
        "review": {"status": "draft", "author": "claude", "reviewer": None},
    }
    raw.update(over)
    return raw


def test_code_line_arrays_are_joined():
    c = ExerciseContent.model_validate(_raw())
    assert c.reference_solution == "def f(n):\n    return n + 1"
    assert c.mutants[0].code == "def f(n):\n    return n - 1"


def test_rejects_unknown_category_and_bad_code():
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(tests=[{"description": "x", "input": "f(1)", "expected": "2",
                                                    "category": "weird", "hidden": True}]))
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(code="EX-1"))


def test_approval_needs_a_reviewer_other_than_the_author():
    assert not ExerciseContent.model_validate(_raw()).is_approved
    same = _raw(review={"status": "approved", "author": "claude", "reviewer": "claude"})
    assert not ExerciseContent.model_validate(same).is_approved
    ok = _raw(review={"status": "approved", "author": "claude", "reviewer": "an"})
    assert ExerciseContent.model_validate(ok).is_approved


def test_limits_require_a_reason():
    with pytest.raises(ValidationError):
        ExerciseContent.model_validate(_raw(limits={"min_hidden": 3}))
    c = ExerciseContent.model_validate(_raw(limits={"min_hidden": 3, "reason": "timing-dependent"}))
    assert c.limits.min_hidden == 3


def test_load_content_file_checks_the_file_name(tmp_path):
    p = tmp_path / "CP-005.json"
    p.write_text(json.dumps(_raw()), encoding="utf-8")
    with pytest.raises(ValueError, match="CP-005"):
        load_content_file(p)
