"""
Shared pytest fixtures — in-memory DB + an authenticated test client.

Phase 1-2 friends beta replaced the single shared APP_TOKEN bearer header
with per-user cookie sessions, so the old `client = TestClient(app)` +
`AUTH = {"Authorization": "Bearer testtoken"}` pattern duplicated across
every test file no longer authenticates anything (every protected route
now 401s on it). Use the `auth_client` fixture below instead: it's a
TestClient already logged in as a fresh, active test user (id available via
`auth_client.test_user_id`) — drop the `headers=AUTH` argument from calls
and use `auth_client` in place of `client`.

Only tests/test_safety_net.py has been migrated to this pattern so far, as
a template. The other test files still carry their own old per-file
DB/TestClient/APP_TOKEN setup and need the same migration:
  - Remove the file's own `client = TestClient(app)`, `AUTH = {...}`,
    `os.environ["APP_TOKEN"] = ...`, and duplicated `clean_db`/`override_get_db`
    (all now provided here).
  - Replace `client.get(..., headers=AUTH)` with `auth_client.get(...)`.
  - A test needing a second, independent user should build one directly
    (see test_safety_net.py's cross-user isolation tests for the pattern:
    create a User row with app.auth.hash_password, POST /api/auth/login).
"""
import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# TestClient talks to http://testserver (no TLS) — a Secure cookie would
# never be sent back, so every "authenticated" request after login would
# silently 401. See config.py's session_cookie_secure docstring.
os.environ.setdefault("SESSION_COOKIE_SECURE", "false")

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


@pytest.fixture
def auth_client(client):
    """A TestClient logged in (session cookie set) as a fresh, active user."""
    db = TestingSession()
    user = User(
        email=TEST_USER_EMAIL,
        password_hash=hash_password(TEST_USER_PASSWORD),
        name="Test User",
        role="user",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    r = client.post("/api/auth/login", json={
        "email": TEST_USER_EMAIL, "password": TEST_USER_PASSWORD, "remember": True,
    })
    assert r.status_code == 200, r.text
    client.test_user_id = user_id
    return client
