"""Informational activity-burn estimate (does not feed the calorie target)."""
from app.activity_burn import activity_kcal


def test_activity_kcal_uses_mets():
    # MET × weight(kg) × hours
    assert activity_kcal("football", 60, 80) == 640    # 8 × 80 × 1
    assert activity_kcal("judo", 60, 80) == 800        # 10 × 80 × 1
    assert activity_kcal("padel", 30, 80) == 280       # 7 × 80 × 0.5
    assert activity_kcal("unknown", 60, 80) == 480     # default MET 6
