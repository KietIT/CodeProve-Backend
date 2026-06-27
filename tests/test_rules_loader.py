from app.features.scoring.rules_loader import get_rule, load_rules


def test_loads_all_axes():
    rules = load_rules()
    for axis in ["understanding", "hypothesis", "prompting", "verification", "testing", "debugging"]:
        assert axis in rules and len(rules[axis]) >= 1
    p1 = get_rule(rules["prompting"], "P1-lazy-prompt")
    assert p1.thresholds["minChars"] == 30
    assert p1.effect["perHit"] == -2


# Every rule id the scoring engine relies on must exist for its axis (guards against
# an accidental rename/deletion when the editable YAML is tuned).
EXPECTED_RULE_IDS = {
    "understanding": {"U1-rushed-start", "U2-explain-again", "U3-explain-back"},
    "hypothesis": {"H1-user-correct", "H2-ai-rescue", "H3-no-plan", "H-base"},
    "prompting": {"P1-lazy-prompt", "P2-repeated", "P3-keyword-fit", "P4-no-constraint"},
    "verification": {"V1-trap-caught", "V1b-trap-missed", "V2-speed-accept", "V3-paste-blind", "V-base"},
    "testing": {"T1-has-tests", "T2-coverage", "T0-none"},
    "debugging": {"D1-fix-success", "D2-ai-dependent", "D-base"},
}


def test_all_expected_rule_ids_present():
    rules = load_rules()
    for axis, ids in EXPECTED_RULE_IDS.items():
        present = {r.id for r in rules[axis]}
        assert ids <= present, f"{axis} missing {ids - present}"


def test_key_thresholds_match_spec():
    rules = load_rules()
    assert get_rule(rules["understanding"], "U1-rushed-start").thresholds["firstPromptDelaySec"] == 20
    assert get_rule(rules["hypothesis"], "H1-user-correct").effect["cap"] == 20
    assert get_rule(rules["hypothesis"], "H-base").effect["base"] == 8
    assert get_rule(rules["prompting"], "P2-repeated").thresholds["similarity"] == 0.85
    assert get_rule(rules["verification"], "V2-speed-accept").thresholds["withinSec"] == 15
    assert get_rule(rules["verification"], "V-base").effect["base"] == 12
    assert get_rule(rules["testing"], "T2-coverage").thresholds["minCoverage"] == 0.7
    assert get_rule(rules["debugging"], "D1-fix-success").effect["perHit"] == 6


def test_get_rule_raises_on_missing():
    import pytest

    rules = load_rules()
    with pytest.raises(KeyError):
        get_rule(rules["prompting"], "P9-nonexistent")
