from app.seed.exercises_seed import EXERCISES


def test_seed_covers_all_levels_and_shapes():
    codes = {e["code"] for e in EXERCISES}
    assert "CP-001" in codes
    assert len([e for e in EXERCISES if e["level"] == "fresher"]) >= 12
    assert len([e for e in EXERCISES if e["level"] == "junior"]) >= 10
    assert len([e for e in EXERCISES if e["level"] == "senior"]) >= 8
    for e in EXERCISES:
        assert {"code", "title", "level", "starter_code", "hint", "summary"} <= set(e)
        assert len(e["tests"]) >= 2


def test_seed_total_count():
    assert len(EXERCISES) == 30


def test_seed_fresher_codes():
    fresher = [e for e in EXERCISES if e["level"] == "fresher"]
    codes = {e["code"] for e in fresher}
    for i in range(1, 13):
        assert f"CP-{i:03d}" in codes, f"Missing CP-{i:03d} in fresher level"


def test_seed_junior_codes():
    junior = [e for e in EXERCISES if e["level"] == "junior"]
    codes = {e["code"] for e in junior}
    for i in range(101, 111):
        assert f"CP-{i}" in codes, f"Missing CP-{i} in junior level"


def test_seed_senior_codes():
    senior = [e for e in EXERCISES if e["level"] == "senior"]
    codes = {e["code"] for e in senior}
    for i in range(201, 209):
        assert f"CP-{i}" in codes, f"Missing CP-{i} in senior level"


def test_seed_all_exercises_have_valid_difficulty():
    valid = {"Easy", "Medium", "Hard"}
    for e in EXERCISES:
        assert e["difficulty"] in valid, f"{e['code']} has invalid difficulty: {e['difficulty']}"


def test_seed_all_exercises_have_domain_keywords():
    for e in EXERCISES:
        assert isinstance(e["domain_keywords"], list), f"{e['code']} domain_keywords not a list"
        assert len(e["domain_keywords"]) >= 3, f"{e['code']} has fewer than 3 domain_keywords"


def test_seed_test_cases_have_required_fields():
    required = {"input_data", "expected_output", "description", "is_hidden", "order_index", "weight"}
    for e in EXERCISES:
        for t in e["tests"]:
            missing = required - set(t)
            assert not missing, f"{e['code']} test case missing fields: {missing}"


def test_seed_verification_trap_exercises():
    trap_codes = {e["code"] for e in EXERCISES if e.get("verification_trap")}
    # At least 5 exercises should have verification_trap=True
    assert len(trap_codes) >= 5, f"Only {len(trap_codes)} exercises have verification_trap=True"
    # Spot-check a few expected ones
    assert "CP-001" in trap_codes
    assert "CP-004" in trap_codes
    assert "CP-201" in trap_codes


def test_seed_no_placeholder_comments():
    """Ensure the ... placeholder from the brief was not left in the file."""
    for e in EXERCISES:
        # starter_code should not consist solely of '...'
        assert e["starter_code"].strip() != "..."
