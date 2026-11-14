"""
Demo seeder: isolated to its own account, gated off by default, local-DB only,
and fully removable.
"""
import pytest

from app import seed_demo
from app.config import settings
from app.models import (
    NutritionDay, Session, Set, Tracker, TrackerLog, User, WeightLog,
)
from tests.conftest import TestingSession, _make_user


@pytest.fixture
def demo_on(monkeypatch):
    monkeypatch.setattr(seed_demo, "SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "enable_dev_seed", True)
    monkeypatch.setattr(settings, "database_url", "sqlite:///./x.sqlite3")


def _count(model, **filters):
    db = TestingSession()
    try:
        return db.query(model).filter_by(**filters).count()
    finally:
        db.close()


def test_refuses_without_the_dev_seed_switch(monkeypatch):
    monkeypatch.setattr(seed_demo, "SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "enable_dev_seed", False)
    with pytest.raises(SystemExit, match="ENABLE_DEV_SEED"):
        seed_demo.seed_demo()
    assert _count(User, email=seed_demo.DEMO_EMAIL) == 0


def test_refuses_a_remote_database(monkeypatch):
    monkeypatch.setattr(seed_demo, "SessionLocal", TestingSession)
    monkeypatch.setattr(settings, "enable_dev_seed", True)
    monkeypatch.setattr(settings, "database_url",
                        "postgresql://u:p@db.railway.internal:5432/railway")
    with pytest.raises(SystemExit, match="not this machine"):
        seed_demo.seed_demo()
    assert _count(User, email=seed_demo.DEMO_EMAIL) == 0


def test_fills_only_the_demo_account(demo_on):
    other = _make_user("real@example.com", "testpassword123")
    seed_demo.seed_demo()

    db = TestingSession()
    try:
        demo = db.query(User).filter_by(email=seed_demo.DEMO_EMAIL).one()
        assert demo.role == "user"
        assert db.query(Session).filter_by(user_id=demo.id).count() > 20
        assert db.query(Set).filter_by(user_id=demo.id).count() > 200
        assert db.query(WeightLog).filter_by(user_id=demo.id).count() > 80
        assert db.query(NutritionDay).filter_by(user_id=demo.id).count() > 80
        assert db.query(Tracker).filter_by(user_id=demo.id).count() == 3
        # The real account gets nothing
        assert db.query(Session).filter_by(user_id=other).count() == 0
        assert db.query(WeightLog).filter_by(user_id=other).count() == 0
    finally:
        db.close()


def test_rerun_is_idempotent_and_reset_removes_everything(demo_on, monkeypatch):
    seed_demo.seed_demo()
    first = _count(Session)
    seed_demo.seed_demo()
    assert _count(Session) == first          # wiped + refilled, not doubled
    assert _count(User, email=seed_demo.DEMO_EMAIL) == 1

    other = _make_user("real@example.com", "testpassword123")
    monkeypatch.setattr("sys.argv", ["seed_demo", "--reset"])
    seed_demo.main()
    assert _count(User, email=seed_demo.DEMO_EMAIL) == 0
    assert _count(Session) == 0 and _count(Set) == 0 and _count(TrackerLog) == 0
    assert _count(User, id=other) == 1       # untouched
