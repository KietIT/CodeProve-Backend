from app.features.scoring.rules_loader import get_rule, load_rules


def test_loads_all_axes():
    rules = load_rules()
    for axis in ["understanding", "hypothesis", "prompting", "verification", "testing", "debugging"]:
        assert axis in rules and len(rules[axis]) >= 1
    p1 = get_rule(rules["prompting"], "P1-lazy-prompt")
    assert p1.thresholds["minChars"] == 30
    assert p1.effect["perHit"] == -2
