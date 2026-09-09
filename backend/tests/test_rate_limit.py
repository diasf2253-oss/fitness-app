"""
Rate limiting on the auth endpoints (app/ratelimit.py).

The limiter is disabled suite-wide by conftest (AUTH_RATE_LIMIT_ENABLED=false)
so the many logins across the suite don't trip it. These tests flip
settings.auth_rate_limit_enabled back on and reset the shared counter, so they
exercise the real 429 behaviour in isolation. monkeypatch restores the flag
after each test.
"""
from app import ratelimit
from app.config import settings


def test_login_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    ratelimit.reset()
    # 10 attempts/min/IP are allowed; each returns 401 (wrong creds), not 429.
    for _ in range(10):
        r = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
        assert r.status_code == 401, r.text
    # The 11th within the window is blocked.
    r = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}
    ratelimit.reset()


def test_join_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    ratelimit.reset()
    body = {"code": "bad-code", "name": "A", "email": "a@example.com", "password": "password123"}
    # 5 attempts/min/IP allowed; each returns 400 (invalid code), not 429.
    for _ in range(5):
        r = client.post("/api/auth/join", json=body)
        assert r.status_code == 400, r.text
    r = client.post("/api/auth/join", json=body)
    assert r.status_code == 429
    ratelimit.reset()


def test_limiter_is_off_by_default_in_tests(client):
    # With the suite default (flag off) many rapid logins never hit 429.
    for _ in range(15):
        r = client.post("/api/auth/login", json={"email": "x@example.com", "password": "nope"})
        assert r.status_code == 401
