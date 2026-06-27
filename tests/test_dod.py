"""
Definition-of-Done integrity test (Task 19).

Verifies that integrity_from_features maps the three integrity bands
correctly without touching the database or calling any external service.
"""

from app.features.attempts.scoring_service import integrity_from_features
from app.features.scoring.features import AxisFeatures


def test_integrity_levels() -> None:
    assert integrity_from_features(AxisFeatures(integrity_flag_total=0)) == "green"
    assert integrity_from_features(AxisFeatures(integrity_flag_total=2)) == "yellow"
    assert integrity_from_features(AxisFeatures(integrity_flag_total=5)) == "red"
