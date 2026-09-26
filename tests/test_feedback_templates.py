import pytest

from app.features.feedback.diagnosis import FINDING_CODES, Finding
from app.features.feedback.templates import FIELDS, TEMPLATES, render

SAMPLE_PARAMS = {
    "asked_for_solution": {"count": 2},
    "submitted_failing": {"passed": 5, "total": 8},
    "hidden_edge_failed": {"failed_categories": ["boundary", "edge"]},
    "partial_fix": {"failed_categories": ["edge"]},
    "trial_and_error": {"failing_runs": 5},
    "integrity_flags": {"paste": 1, "focus_lost": 0},
}


def finding(code: str, **params) -> Finding:
    # Only the code and params matter for rendering.
    return Finding(code=code, axis="testing", kind="risk", severity="medium", params=params)


def test_every_code_has_both_locales_and_every_field():
    assert set(TEMPLATES) == set(FINDING_CODES)
    for code, by_locale in TEMPLATES.items():
        assert set(by_locale) == {"vi", "en"}, code
        for locale, texts in by_locale.items():
            assert set(texts) == {"what_happened", "why_it_matters", "how_to_improve", "practice"}, (code, locale)
            assert all(isinstance(t, str) and t.strip() for t in texts.values()), (code, locale)


@pytest.mark.parametrize("code", FINDING_CODES)
@pytest.mark.parametrize("locale", ["vi", "en"])
def test_every_template_renders_with_and_without_params(code, locale):
    for params in (SAMPLE_PARAMS.get(code, {}), {}):
        for next_exercise in ("CP-105", None):
            out = render(finding(code, **params), locale, next_exercise)
            assert set(out) == set(FIELDS)
            assert all(out[f].strip() for f in FIELDS)
            assert "{" not in "".join(out.values()), out  # no unfilled placeholder


def test_params_are_rendered_readably():
    out = render(finding("hidden_edge_failed", failed_categories=["boundary", "edge"]), "vi", None)
    assert "nhóm biên và đặc biệt" in out["what_happened"]
    out = render(finding("submitted_failing", passed=5, total=8), "en", None)
    assert "5/8" in out["what_happened"]


def test_try_next_names_the_suggested_exercise():
    assert "CP-105" in render(finding("no_hypothesis"), "vi", "CP-105")["try_next"]
    assert "CP-" not in render(finding("no_hypothesis"), "vi", None)["try_next"]


def test_unknown_locale_falls_back_to_vietnamese():
    assert render(finding("no_hypothesis"), "fr", None) == render(finding("no_hypothesis"), "vi", None)
