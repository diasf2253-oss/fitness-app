"""
Supabase Auth — the deep coverage behind the safety net's auth checks.

Three layers, mirroring app/auth.py:
  1. Token verification: only a genuine, unexpired, signed-in user's token
     from *this* project gets through (app/supabase_auth.py).
  2. Account linking: a pre-Supabase account attaches to the Supabase login
     with the same email — but only once Supabase confirms that email is
     verified, and never re-links an already linked account.
  3. Who's allowed in: invite code → pending → admin approval, with /me
     reporting the status and data routes refusing anyone not active.

Everything Supabase-side is faked by conftest's `fake_supabase` fixture.
"""
import httpx
import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from jwt.algorithms import ECAlgorithm

from app.core.config import settings
from app.models import InviteCode, User
from tests.conftest import (
    PUBLIC_JWK,
    TestingSession,
    _make_user,
    make_token,
    sign_in,
    uid_for,
)


def _bearer(client, token):
    client.headers["Authorization"] = f"Bearer {token}"
    return client


def _user(email):
    db = TestingSession()
    try:
        return db.query(User).filter(User.email == email).first()
    finally:
        db.close()


def _invite(code="welcome-friend", max_uses=None, uses=0, active=True):
    db = TestingSession()
    db.add(InviteCode(code=code, max_uses=max_uses, uses=uses, active=active))
    db.commit()
    db.close()
    return code


def _invite_uses(code):
    db = TestingSession()
    try:
        return db.query(InviteCode).filter(InviteCode.code == code).one().uses
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Token verification
# ---------------------------------------------------------------------------

class TestTokenVerification:
    EMAIL = "test@example.com"

    def _account(self):
        _make_user(self.EMAIL)
        return uid_for(self.EMAIL)

    def test_no_token_is_401_with_a_bearer_challenge(self, client):
        r = client.get("/api/settings")
        assert r.status_code == 401
        assert r.headers.get("www-authenticate") == "Bearer"

    def test_a_valid_token_gets_in(self, client):
        uid = self._account()
        assert _bearer(client, make_token(uid, self.EMAIL)).get("/api/settings").status_code == 200

    def test_garbage_is_rejected(self, client):
        assert _bearer(client, "not-a-jwt").get("/api/settings").status_code == 401

    def test_expired_token_is_rejected(self, client):
        uid = self._account()
        token = make_token(uid, self.EMAIL, expires_in=-120)
        assert _bearer(client, token).get("/api/settings").status_code == 401

    def test_another_projects_token_is_rejected(self, client):
        uid = self._account()
        token = make_token(uid, self.EMAIL, iss="https://some-other-project.supabase.co/auth/v1")
        assert _bearer(client, token).get("/api/settings").status_code == 401

    def test_wrong_audience_is_rejected(self, client):
        uid = self._account()
        token = make_token(uid, self.EMAIL, aud="something-else")
        assert _bearer(client, token).get("/api/settings").status_code == 401

    def test_public_api_keys_are_not_user_tokens(self, client):
        """The anon / service_role keys are JWTs too — they must never pass as
        a signed-in user, even if they verify."""
        uid = self._account()
        for role in ("anon", "service_role"):
            token = make_token(uid, self.EMAIL, role=role)
            assert _bearer(client, token).get("/api/settings").status_code == 401, role

    def test_anonymous_sign_ins_are_rejected(self, client):
        uid = self._account()
        token = make_token(uid, self.EMAIL, is_anonymous=True)
        assert _bearer(client, token).get("/api/settings").status_code == 401

    def test_token_signed_by_someone_elses_key_is_rejected(self, client):
        """Right key id, wrong private key — a forgery."""
        uid = self._account()
        forger = ec.generate_private_key(ec.SECP256R1())
        token = make_token(uid, self.EMAIL, key=forger)
        assert _bearer(client, token).get("/api/settings").status_code == 401

    def test_legacy_hs256_and_unsigned_tokens_are_rejected(self, client):
        uid = self._account()
        hs256 = make_token(uid, self.EMAIL, key="a-shared-secret-of-thirty-two-bytes!", algorithm="HS256")
        assert _bearer(client, hs256).get("/api/settings").status_code == 401
        unsigned = jwt.encode({"sub": uid, "email": self.EMAIL, "role": "authenticated",
                               "aud": "authenticated", "iss": settings.supabase_issuer},
                              None, algorithm="none")
        assert _bearer(client, unsigned).get("/api/settings").status_code == 401

    def test_unknown_key_id_does_not_hammer_supabase(self, client, fake_supabase):
        uid = self._account()
        assert _bearer(client, make_token(uid, self.EMAIL)).get("/api/settings").status_code == 200
        assert fake_supabase.jwks_fetches == 1
        for _ in range(5):
            r = _bearer(client, make_token(uid, self.EMAIL, kid="no-such-key")).get("/api/settings")
            assert r.status_code == 401
        assert fake_supabase.jwks_fetches == 1   # the cached set was fetched moments ago

    def test_a_rotated_in_key_works(self, client, fake_supabase):
        """Supabase rotates to a new signing key: tokens with the new key id
        verify once the key set is (re)fetched."""
        uid = self._account()
        new_key = ec.generate_private_key(ec.SECP256R1())
        new_jwk = {**ECAlgorithm.to_jwk(new_key.public_key(), as_dict=True),
                   "kid": "rotated-key", "alg": "ES256", "use": "sig"}
        fake_supabase.jwks = {"keys": [PUBLIC_JWK, new_jwk]}
        token = make_token(uid, self.EMAIL, key=new_key, kid="rotated-key")
        assert _bearer(client, token).get("/api/settings").status_code == 200

    def test_supabase_unreachable_on_a_cold_cache_is_503(self, client, monkeypatch):
        from app.core import supabase_auth

        def down():
            raise httpx.ConnectError("no route to host")

        monkeypatch.setattr(supabase_auth, "_fetch_jwks", down)
        uid = self._account()
        r = _bearer(client, make_token(uid, self.EMAIL)).get("/api/settings")
        assert r.status_code == 503

    def test_unconfigured_server_says_so(self, client, monkeypatch):
        uid = self._account()
        token = make_token(uid, self.EMAIL)
        monkeypatch.setattr(settings, "supabase_url", "")
        r = _bearer(client, token).get("/api/settings")
        assert r.status_code == 503
        assert "SUPABASE_URL" in r.json()["detail"]

    def test_a_supabase_token_is_not_an_ingest_token(self, client):
        """Apple Health ingest keeps its own per-user bearer credential."""
        uid = self._account()
        r = _bearer(client, make_token(uid, self.EMAIL)).post("/api/ingest/health", json={})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# 2. Linking pre-Supabase accounts by verified email
# ---------------------------------------------------------------------------

class TestAccountLinking:
    def test_existing_account_links_on_first_sign_in(self, client):
        user_id = _make_user("friend@example.com", linked=False)
        sign_in(client, "friend@example.com")

        r = client.get("/api/auth/me")

        assert r.status_code == 200, r.text
        assert r.json()["id"] == user_id
        assert _user("friend@example.com").supabase_uid == uid_for("friend@example.com")
        assert client.get("/api/settings").status_code == 200

    def test_email_match_is_case_insensitive(self, client):
        _make_user("friend@example.com", linked=False)
        _bearer(client, make_token(uid_for("friend@example.com"), "Friend@Example.COM"))
        assert client.get("/api/auth/me").status_code == 200

    def test_unverified_email_never_links(self, client, fake_supabase):
        _make_user("friend@example.com", linked=False)
        fake_supabase.email_confirmed = False
        sign_in(client, "friend@example.com")

        r = client.get("/api/auth/me")

        assert r.status_code == 403 and r.json()["detail"] == "no_account"
        assert _user("friend@example.com").supabase_uid is None

    def test_a_linked_account_is_never_relinked(self, client):
        """Same email, different Supabase user: hands off the existing account."""
        _make_user("friend@example.com")   # linked to uid_for(...)
        sign_in(client, "friend@example.com", uid="a-different-supabase-user")

        r = client.get("/api/auth/me")

        assert r.status_code == 403 and r.json()["detail"] == "no_account"
        assert _user("friend@example.com").supabase_uid == uid_for("friend@example.com")

    def test_signed_in_with_no_account_at_all(self, client):
        sign_in(client, "stranger@example.com")
        r = client.get("/api/auth/me")
        assert r.status_code == 403 and r.json()["detail"] == "no_account"
        assert client.get("/api/settings").status_code == 403


# ---------------------------------------------------------------------------
# 3. Who's allowed in: statuses, /me, invite codes, approval
# ---------------------------------------------------------------------------

class TestStatuses:
    def test_pending_account_sees_its_status_but_no_data(self, client):
        _make_user("waiting@example.com", status="pending")
        sign_in(client, "waiting@example.com")
        assert client.get("/api/auth/me").json()["status"] == "pending"
        r = client.get("/api/routines")
        assert r.status_code == 403 and r.json()["detail"] == "pending_approval"

    def test_disabled_account_sees_its_status_but_no_data(self, client):
        _make_user("gone@example.com", status="disabled")
        sign_in(client, "gone@example.com")
        assert client.get("/api/auth/me").json()["status"] == "disabled"
        r = client.get("/api/routines")
        assert r.status_code == 403 and r.json()["detail"] == "account_disabled"

    def test_last_seen_is_recorded(self, auth_client):
        assert _user("test@example.com").last_login_at is None
        auth_client.get("/api/settings")
        assert _user("test@example.com").last_login_at is not None


class TestJoin:
    def test_invite_code_creates_a_pending_account(self, client):
        code = _invite()
        sign_in(client, "newcomer@example.com")

        r = client.post("/api/auth/join", json={"code": code, "name": "  New Comer "})

        assert r.status_code == 200, r.text
        assert r.json() == {"status": "pending"}
        user = _user("newcomer@example.com")
        assert user.status == "pending" and user.name == "New Comer"
        assert user.supabase_uid == uid_for("newcomer@example.com")
        assert user.password_hash is None
        assert _invite_uses(code) == 1
        assert client.get("/api/auth/me").json()["status"] == "pending"

    def test_full_journey_join_then_approval(self, client):
        code = _invite()
        sign_in(client, "newcomer@example.com")
        client.post("/api/auth/join", json={"code": code, "name": "New Comer"})
        new_id = _user("newcomer@example.com").id

        _make_user("admin@example.com", role="admin")
        sign_in(client, "admin@example.com")
        assert client.post(f"/api/admin/users/{new_id}/approve").status_code == 200

        sign_in(client, "newcomer@example.com")
        assert client.get("/api/settings").status_code == 200

    def test_bad_code_creates_nothing(self, client):
        _invite()
        sign_in(client, "newcomer@example.com")
        r = client.post("/api/auth/join", json={"code": "guessed", "name": "X"})
        assert r.status_code == 400
        assert _user("newcomer@example.com") is None

    def test_used_up_or_inactive_codes_are_refused(self, client):
        _invite("full", max_uses=1, uses=1)
        _invite("off", active=False)
        sign_in(client, "newcomer@example.com")
        for code in ("full", "off"):
            assert client.post("/api/auth/join", json={"code": code, "name": "X"}).status_code == 400

    def test_last_use_taken_mid_join_is_refused(self, client, monkeypatch):
        """Two people race for the last use of a code: the one whose claim
        lands second gets a clean 'invalid' and no account (the use count is
        re-checked by the database, not trusted from an earlier read)."""
        import app.routers.auth as auth_router
        code = _invite("last-one", max_uses=1)

        def rival_takes_it_first(signed_in):
            db = TestingSession()
            db.query(InviteCode).filter(InviteCode.code == code).one().uses = 1
            db.commit()
            db.close()
            return True
        monkeypatch.setattr(auth_router, "email_confirmed", rival_takes_it_first)

        sign_in(client, "second@example.com")
        r = client.post("/api/auth/join", json={"code": code, "name": "Second"})
        assert r.status_code == 400
        assert _user("second@example.com") is None
        assert _invite_uses(code) == 1

    def test_unverified_email_cannot_join(self, client, fake_supabase):
        code = _invite()
        fake_supabase.email_confirmed = False
        sign_in(client, "newcomer@example.com")
        r = client.post("/api/auth/join", json={"code": code, "name": "X"})
        assert r.status_code == 403
        assert _user("newcomer@example.com") is None
        assert _invite_uses(code) == 0

    def test_joining_twice_is_harmless(self, client):
        code = _invite()
        sign_in(client, "newcomer@example.com")
        client.post("/api/auth/join", json={"code": code, "name": "X"})
        r = client.post("/api/auth/join", json={"code": code, "name": "X"})
        assert r.status_code == 200 and r.json() == {"status": "pending"}
        assert _invite_uses(code) == 1

    def test_existing_account_links_instead_of_joining(self, client):
        code = _invite()
        _make_user("old-timer@example.com", linked=False)
        sign_in(client, "old-timer@example.com")
        r = client.post("/api/auth/join", json={"code": code, "name": "X"})
        assert r.status_code == 200 and r.json() == {"status": "active"}
        assert _user("old-timer@example.com").supabase_uid == uid_for("old-timer@example.com")
        assert _invite_uses(code) == 0

    def test_email_owned_by_another_login_is_a_conflict(self, client):
        code = _invite()
        _make_user("taken@example.com")
        sign_in(client, "taken@example.com", uid="someone-else-entirely")
        r = client.post("/api/auth/join", json={"code": code, "name": "X"})
        assert r.status_code == 409

    def test_join_needs_a_sign_in(self, client):
        code = _invite()
        assert client.post("/api/auth/join", json={"code": code, "name": "X"}).status_code == 401

    def test_join_needs_an_email_on_the_login(self, client):
        code = _invite()
        _bearer(client, make_token("phone-only-user", ""))
        assert client.post("/api/auth/join", json={"code": code, "name": "X"}).status_code == 400
