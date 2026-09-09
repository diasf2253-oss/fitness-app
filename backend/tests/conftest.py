"""
Shared pytest fixtures — in-memory DB + an authenticated test client.

Phase 1-2 friends beta replaced the single shared APP_TOKEN bearer header
with per-user cookie sessions, so the old `client = TestClient(app)` +
`AUTH = {"Authorization": "Bearer testtoken"}` pattern no longer
authenticates anything (every protected route now 401s on it). The whole
suite has been migrated to the fixtures below; new tests should use them
too rather than re-introducing per-file DB/TestClient/token setup.

Patterns for new tests:
  - Take `auth_client` and drop any `headers=AUTH`: it's a TestClient
    already logged in as a fresh, active user (id via
    `auth_client.test_user_id`). Use plain `client` for the
    unauthenticated case (a protected route returns 401).
  - Seeding rows straight into the DB? Import `TestingSession` from here and
    set `user_id=auth_client.test_user_id` on every row — every data table
    is user-scoped and the endpoints filter by the caller's id (the two
    exceptions: `Exercise.user_id` is optional, and `TrackerLog` has no
    user_id, being reached through its Tracker).
  - Apple Health ingest routes (`/api/ingest/health*`) authenticate with the
    per-user bearer `ingest_token`, not the cookie — read it from
    `auth_client.get("/api/auth/me").json()["ingest_token"]` and send it as
    `Authorization: Bearer <token>` (see test_health_ingest.py).
  - A route behind `require_admin` needs `admin_client` instead of
    `auth_client` (same shape, role='admin').
  - A test needing a second, independent user builds one directly (see
    test_safety_net.py's cross-user isolation tests: create a User row with
    app.auth.hash_password, POST /api/auth/login on a second client).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# TestClient talks to http://testserver (no TLS) — a Secure cookie would
# never be sent back, so every "authenticated" request after login would
# silently 401. See config.py's session_cookie_secure docstring.
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")
# The auth endpoints carry an IP rate limit; the suite logs in on nearly every
# test, so disable it globally here. test_rate_limit.py flips
# settings.auth_rate_limit_enabled back on per-test to exercise it.
os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")
# The Coach is gated on ANTHROPIC_API_KEY. Put an empty key on the
# environment (which outranks any real key in a dev .env) BEFORE the app —
# and therefore config's settings singleton — imports, so coach endpoints
# 503 deterministically in tests. An explicit key exported in the shell
# still wins, for anyone deliberately exercising the live coach.
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.db import Base, get_db
from app.main import app
from app.models import User

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clean_db():
    """Fresh tables per test; claim the get_db override, then hand it back."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    previous = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db
    yield
    if previous is not None:
        app.dependency_overrides[get_db] = previous


@pytest.fixture
def client():
    return TestClient(app)


TEST_USER_EMAIL = "test@example.com"
TEST_USER_PASSWORD = "testpassword123"
ADMIN_USER_EMAIL = "admin@example.com"


def _make_user(email, password, *, role="user", name="Test User"):
    """Create an active account and return its id."""
    db = TestingSession()
    user = User(
        email=email,
        password_hash=hash_password(password),
        name=name,
        role=role,
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


@pytest.fixture
def admin_client(client):
    """A TestClient logged in as an admin — for routes behind require_admin."""
    user_id = _make_user(ADMIN_USER_EMAIL, TEST_USER_PASSWORD,
                         role="admin", name="Test Admin")
    r = client.post("/api/auth/login", json={
        "email": ADMIN_USER_EMAIL, "password": TEST_USER_PASSWORD, "remember": True,
    })
    assert r.status_code == 200, r.text
    client.test_user_id = user_id
    return client


@pytest.fixture
def auth_client(client):
    """A TestClient logged in (session cookie set) as a fresh, active user."""
    user_id = _make_user(TEST_USER_EMAIL, TEST_USER_PASSWORD)

    r = client.post("/api/auth/login", json={
        "email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD, "remember": True,
    })
    assert r.status_code == 200, r.text
    client.test_user_id = user_id
    return client
