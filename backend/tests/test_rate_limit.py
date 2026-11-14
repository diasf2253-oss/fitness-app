"""
Rate limiting on the signup endpoint (app/ratelimit.py).

Password sign-in itself now happens at Supabase, which rate-limits it; what's
left here is /api/auth/join, the invite-code check. The limiter is disabled
suite-wide by conftest (AUTH_RATE_LIMIT_ENABLED=false); these tests flip
settings.auth_rate_limit_enabled back on and reset the shared counter, so they
exercise the real 429 behaviour in isolation. monkeypatch restores the flag
after each test.
"""
from app.core import ratelimit
from app.core.config import settings
from tests.conftest import sign_in

BAD_CODE = {"code": "bad-code", "name": "A"}


def test_join_is_rate_limited(client, monkeypatch):
    monkeypatch.setattr(settings, "auth_rate_limit_enabled", True)
    ratelimit.reset()
    sign_in(client, "newcomer@example.com")   # a Supabase login with no account yet
    # 5 attempts/min/IP allowed; each returns 400 (invalid code), not 429.
    for _ in range(5):
        r = client.post("/api/auth/join", json=BAD_CODE)
        assert r.status_code == 400, r.text
    r = client.post("/api/auth/join", json=BAD_CODE)
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers}
    ratelimit.reset()


def test_limiter_is_off_by_default_in_tests(client):
    sign_in(client, "newcomer@example.com")
    # With the suite default (flag off) many rapid attempts never hit 429.
    for _ in range(15):
        assert client.post("/api/auth/join", json=BAD_CODE).status_code == 400
