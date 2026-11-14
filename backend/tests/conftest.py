"""
Shared pytest fixtures — in-memory DB, faked Supabase, signed-in test clients.

Auth is Supabase Auth now: the browser sends a Supabase access token (a
signed JWT) as `Authorization: Bearer <token>`, and app/supabase_auth.py
verifies it against the project's public keys. The suite never talks to a
real Supabase project. Instead:
  - an EC P-256 key pair is generated once per test run; its public half is
    served as the project's key set (JWKS) by a fake, so tokens signed with
    make_token() verify exactly like real ones;
  - Supabase's Auth API (the "is this email confirmed?" lookup and the admin
    reset-link call) is faked by the autouse `fake_supabase` fixture, whose
    state tests can tweak (e.g. `fake_supabase.email_confirmed = False`).

Patterns for new tests:
  - Take `auth_client`: a TestClient already signed in as a fresh, active
    user (id via `auth_client.test_user_id`). Use plain `client` for the
    signed-out case (a protected route returns 401).
  - Seeding rows straight into the DB? Import `TestingSession` from here and
    set `user_id=auth_client.test_user_id` on every row — every data table
    is user-scoped and the endpoints filter by the caller's id (the two
    exceptions: `Exercise.user_id` is optional, and `TrackerLog` has no
    user_id, being reached through its Tracker).
  - A second, independent user: `_make_user("other@example.com")`, then
    `sign_in(client, "other@example.com")` switches the client to them (see
    test_safety_net.py's cross-user isolation test). `auth_client` and
    `client` are the same object within one test.
  - Apple Health ingest routes (`/api/ingest/health*`) authenticate with the
    per-user bearer `ingest_token`, not a Supabase token — read it from
    `auth_client.get("/api/auth/me").json()["ingest_token"]` and send it as
    `Authorization: Bearer <token>` (see test_health_ingest.py).
  - A route behind `require_admin` needs `admin_client` instead of
    `auth_client` (same shape, role='admin').
  - A Supabase login with no app account yet (the invite-code flow):
    `sign_in(client, "new@example.com")` without creating a user.
"""
import os
import time
import types
import uuid

# Point the app at a fake Supabase project BEFORE it (and config's settings
# singleton) imports. Forced, not setdefault: tests must never reach a real
# project, whatever the shell or backend/.env says.
TEST_SUPABASE_URL = "https://test-project.supabase.co"
os.environ["SUPABASE_URL"] = TEST_SUPABASE_URL
os.environ["SUPABASE_PUBLISHABLE_KEY"] = "sb_publishable_test"
os.environ["SUPABASE_SECRET_KEY"] = ""

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
# The join endpoint carries an IP rate limit; disable it globally here.
# test_rate_limit.py flips settings.auth_rate_limit_enabled back on per-test.
os.environ.setdefault("AUTH_RATE_LIMIT_ENABLED", "false")
# The Coach is gated on ANTHROPIC_API_KEY. Put an empty key on the
# environment (which outranks any real key in a dev .env) BEFORE the app —
# and therefore config's settings singleton — imports, so coach endpoints
# 503 deterministically in tests. An explicit key exported in the shell
# still wins, for anyone deliberately exercising the live coach.
os.environ.setdefault("ANTHROPIC_API_KEY", "")

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import supabase_auth
from app.core.config import settings
from app.core.db import Base, get_db
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


# ---------------------------------------------------------------------------
# Fake Supabase project
# ---------------------------------------------------------------------------

TEST_KID = "test-signing-key"
_SIGNING_KEY = ec.generate_private_key(ec.SECP256R1())
PUBLIC_JWK = {
    **ECAlgorithm.to_jwk(_SIGNING_KEY.public_key(), as_dict=True),
    "kid": TEST_KID, "alg": "ES256", "use": "sig",
}


def make_token(uid, email="", *, role="authenticated", aud="authenticated",
               iss=None, expires_in=3600, key=None, kid=TEST_KID,
               algorithm="ES256", **extra_claims):
    """A Supabase-shaped access token, signed with the test key unless
    `key` says otherwise. Every knob exists so tests can forge bad ones."""
    now = int(time.time())
    claims = {
        "sub": uid, "email": email, "role": role, "aud": aud,
        "iss": iss or settings.supabase_issuer,
        "iat": now, "exp": now + expires_in,
        "aal": "aal1", "session_id": "test-session", "is_anonymous": False,
        **extra_claims,
    }
    return jwt.encode(claims, key or _SIGNING_KEY, algorithm=algorithm,
                      headers={"kid": kid})


def uid_for(email):
    """Deterministic fake Supabase user id per email."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"supabase-test:{email.strip().lower()}"))


def sign_in(client, email, uid=None):
    """Make `client` send a valid access token for this email from now on."""
    client.headers["Authorization"] = f"Bearer {make_token(uid or uid_for(email), email.lower())}"
    return client


@pytest.fixture(autouse=True)
def fake_supabase(monkeypatch):
    """No network, ever: the key set and the Auth API are faked per test.

    Tweak the returned state to steer a test:
      .jwks             what the JWKS endpoint returns
      .email_confirmed  what the "is this email verified?" lookup answers
      .admin_response   an httpx.Response for the admin reset-link call
                        (None ⇒ any admin call fails the test)
      .admin_calls      [(path, payload), ...] admin calls made so far
      .admin_headers    the headers the last admin call carried
      .jwks_fetches     how many times the key set was fetched
    """
    supabase_auth.reset_key_cache()
    state = types.SimpleNamespace(
        jwks={"keys": [PUBLIC_JWK]}, email_confirmed=True,
        admin_response=None, admin_calls=[], admin_headers=None, jwks_fetches=0,
    )

    def fake_fetch_jwks():
        state.jwks_fetches += 1
        return state.jwks

    def fake_fetch_auth_user(token):
        return {"email_confirmed_at": "2026-01-01T00:00:00Z" if state.email_confirmed else None}

    def fake_post_admin(path, payload, headers):
        state.admin_calls.append((path, payload))
        state.admin_headers = headers
        if state.admin_response is None:
            raise AssertionError(f"unexpected Supabase admin call: {path}")
        return state.admin_response

    monkeypatch.setattr(supabase_auth, "_fetch_jwks", fake_fetch_jwks)
    monkeypatch.setattr(supabase_auth, "fetch_auth_user", fake_fetch_auth_user)
    monkeypatch.setattr(supabase_auth, "_post_admin", fake_post_admin)
    yield state
    supabase_auth.reset_key_cache()


# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    return TestClient(app)


TEST_USER_EMAIL = "test@example.com"
ADMIN_USER_EMAIL = "admin@example.com"


def _make_user(email, *, role="user", name="Test User", status="active", linked=True):
    """Create an account and return its id. `linked` = already signed in
    through Supabase once (supabase_uid set to uid_for(email))."""
    db = TestingSession()
    user = User(
        email=email.strip().lower(),
        supabase_uid=uid_for(email) if linked else None,
        name=name,
        role=role,
        status=status,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()
    return user_id


@pytest.fixture
def admin_client(client):
    """A TestClient signed in as an admin — for routes behind require_admin."""
    user_id = _make_user(ADMIN_USER_EMAIL, role="admin", name="Test Admin")
    sign_in(client, ADMIN_USER_EMAIL)
    client.test_user_id = user_id
    return client


@pytest.fixture
def auth_client(client):
    """A TestClient signed in (Supabase bearer token) as a fresh, active user."""
    user_id = _make_user(TEST_USER_EMAIL)
    sign_in(client, TEST_USER_EMAIL)
    client.test_user_id = user_id
    return client
