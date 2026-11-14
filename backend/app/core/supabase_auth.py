"""
Talking to Supabase Auth — the service that runs sign-in for this app.

How a request is authenticated now:
  1. The browser signs in with Supabase (email + password, or Google) and
     gets an *access token*: a short-lived JWT ("JSON Web Token" — a signed
     note saying "this is user <id>, valid until <time>").
  2. It sends that token on every API call as `Authorization: Bearer <token>`.
  3. verify_access_token() below checks the signature against the project's
     public keys, plus the expiry, issuer and audience. If it holds up, we
     know which Supabase user is calling — without asking Supabase each time.

The public keys come from the project's JWKS endpoint ("JSON Web Key Set":
the public halves of the keys Supabase signs tokens with). They're cached in
memory for a few minutes; Supabase asks clients not to cache them for longer,
so a rotated or revoked key stops working here quickly.

Only asymmetric keys (ES256 / RS256) are accepted. Supabase projects still on
the legacy shared JWT secret (HS256) must switch to signing keys first
(Supabase dashboard → Project Settings → JWT Keys) — see notes/runbooks/SUPABASE.md.

Two things a token can't tell us need a call to Supabase itself:
  - email_is_confirmed(): whether the address has been verified (there is no
    trustworthy claim for it). Asked only when linking an account by email
    or joining — i.e. once per person, not per request.
  - generate_recovery_link(): the admin's "password reset link" button.

The HTTP helpers (_fetch_jwks, fetch_auth_user, _post_admin) are small module
functions so the test suite can swap them for fakes — tests never hit the
network.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import httpx
import jwt

from app.core.config import settings

log = logging.getLogger(__name__)

AUDIENCE = "authenticated"
_ALLOWED_ALGORITHMS = ("ES256", "RS256")
_JWKS_TTL_SECONDS = 600         # Supabase: don't cache the key set longer than ~10 min
_JWKS_MIN_REFETCH_SECONDS = 30  # an unknown key id triggers a refetch, at most this often
_HTTP_TIMEOUT = httpx.Timeout(5.0)


class AuthNotConfigured(Exception):
    """A setting this feature needs (named in the message) is empty."""


class AuthServerUnavailable(Exception):
    """Supabase couldn't be reached, or answered with something unusable."""


class InvalidToken(Exception):
    """The token is missing, malformed, expired, forged, or not a user token."""


class NoSuchAuthUser(Exception):
    """Supabase has no account for this email address."""


@dataclass(frozen=True)
class Identity:
    """Who a verified token belongs to."""
    uid: str     # the Supabase user id (the token's `sub`) — stable for life
    email: str   # lower-cased; may be '' for accounts without an email


# ---------------------------------------------------------------------------
# Public keys (JWKS), cached per process
# ---------------------------------------------------------------------------

class _KeyCache:
    def __init__(self) -> None:
        self.keys: dict[str, jwt.PyJWK] = {}
        self.fetched_at = float("-inf")
        self.lock = threading.Lock()

    def clear(self) -> None:
        with self.lock:
            self.keys = {}
            self.fetched_at = float("-inf")


_key_cache = _KeyCache()


def reset_key_cache() -> None:
    """Forget the cached public keys (tests; also harmless at runtime)."""
    _key_cache.clear()


def _fetch_jwks() -> dict:
    """GET the project's public signing keys. Replaced by a fake in tests."""
    response = httpx.get(
        f"{settings.supabase_issuer}/.well-known/jwks.json", timeout=_HTTP_TIMEOUT
    )
    response.raise_for_status()
    return response.json()


def _signing_key(kid: str) -> jwt.PyJWK | None:
    """The public key with this key id, refreshing the cache when it's stale
    or the id is new (a freshly rotated key)."""
    with _key_cache.lock:
        now = time.monotonic()
        age = now - _key_cache.fetched_at
        stale = age > _JWKS_TTL_SECONDS
        unknown = kid not in _key_cache.keys and age > _JWKS_MIN_REFETCH_SECONDS
        if stale or unknown:
            try:
                data = _fetch_jwks()
            except (httpx.HTTPError, ValueError) as exc:
                if not _key_cache.keys:
                    raise AuthServerUnavailable("couldn't fetch Supabase's public keys") from exc
                # Keep serving the keys we have through a blip; retry soon.
                log.warning("Supabase JWKS refresh failed (%s); using cached keys", exc)
                _key_cache.fetched_at = now - _JWKS_TTL_SECONDS + _JWKS_MIN_REFETCH_SECONDS
            else:
                keys: dict[str, jwt.PyJWK] = {}
                for entry in data.get("keys", []):
                    entry_kid = entry.get("kid")
                    if not entry_kid:
                        continue
                    try:
                        keys[entry_kid] = jwt.PyJWK.from_dict(entry)
                    except jwt.PyJWTError:
                        log.warning("Skipping a Supabase signing key PyJWT can't load (kid=%s)", entry_kid)
                _key_cache.keys = keys
                _key_cache.fetched_at = now
        return _key_cache.keys.get(kid)


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

def verify_access_token(token: str) -> Identity:
    """
    Return who `token` belongs to, or raise InvalidToken.

    Rejects anything that isn't a signed-in user's token from *this* project:
    wrong signature, expired, another project's issuer, the public anon /
    service_role keys (role isn't 'authenticated', issuer is just
    'supabase'), and anonymous sign-ins.
    """
    if not settings.supabase_url:
        raise AuthNotConfigured("SUPABASE_URL")
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise InvalidToken("malformed token") from exc

    algorithm = header.get("alg")
    if algorithm not in _ALLOWED_ALGORITHMS:
        if algorithm == "HS256":
            log.error(
                "Got an HS256 Supabase token: this project still signs with the "
                "legacy shared secret. Switch it to JWT signing keys in the "
                "Supabase dashboard (Project Settings → JWT Keys)."
            )
        raise InvalidToken(f"unsupported signing algorithm {algorithm!r}")

    kid = header.get("kid")
    signing_key = _signing_key(kid) if kid else None
    if signing_key is None:
        raise InvalidToken("unknown signing key")
    if signing_key.algorithm_name != algorithm:
        raise InvalidToken("signing key / algorithm mismatch")

    try:
        claims = jwt.decode(
            token,
            key=signing_key.key,
            algorithms=[algorithm],
            audience=AUDIENCE,
            issuer=settings.supabase_issuer,
            leeway=30,  # tolerate small clock drift between Supabase and us
            options={"require": ["exp", "iat", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc)) from exc

    if claims.get("role") != "authenticated" or claims.get("is_anonymous"):
        raise InvalidToken("not a signed-in user's token")
    subject = str(claims.get("sub") or "").strip()
    if not subject:
        raise InvalidToken("token has no subject")

    return Identity(uid=subject, email=str(claims.get("email") or "").strip().lower())


# ---------------------------------------------------------------------------
# Calls to the Auth server
# ---------------------------------------------------------------------------

def fetch_auth_user(token: str) -> dict:
    """GET /auth/v1/user as the token's owner. Replaced by a fake in tests."""
    if not settings.supabase_publishable_key:
        raise AuthNotConfigured("SUPABASE_PUBLISHABLE_KEY")
    try:
        response = httpx.get(
            f"{settings.supabase_issuer}/user",
            headers={
                "apikey": settings.supabase_publishable_key,
                "Authorization": f"Bearer {token}",
            },
            timeout=_HTTP_TIMEOUT,
        )
    except httpx.HTTPError as exc:
        raise AuthServerUnavailable("couldn't reach Supabase Auth") from exc
    if response.status_code in (401, 403):
        raise InvalidToken("Supabase rejected the token")
    if response.status_code != 200:
        raise AuthServerUnavailable(f"Supabase Auth answered HTTP {response.status_code}")
    try:
        return response.json()
    except ValueError as exc:
        raise AuthServerUnavailable("Supabase Auth sent an unreadable reply") from exc


def email_is_confirmed(token: str) -> bool:
    """
    True when Supabase says the token owner's email address is verified.

    This is what makes linking-by-email safe: an existing app account is
    only ever attached to a Supabase login that has proven it owns that
    address — the same bar as a "forgot password" email.
    """
    return bool(fetch_auth_user(token).get("email_confirmed_at"))


def _admin_headers() -> dict[str, str]:
    key = settings.supabase_secret_key
    if not key:
        raise AuthNotConfigured("SUPABASE_SECRET_KEY")
    headers = {"apikey": key}
    # New-style secret keys (sb_secret_…) aren't JWTs and travel only in the
    # `apikey` header. The legacy service_role key is a JWT, and the Auth
    # admin API also wants it as the bearer token.
    if not key.startswith("sb_"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _post_admin(path: str, payload: dict, headers: dict[str, str]) -> httpx.Response:
    """POST to an Auth admin endpoint. Replaced by a fake in tests."""
    try:
        return httpx.post(
            f"{settings.supabase_issuer}{path}",
            json=payload,
            headers=headers,
            timeout=httpx.Timeout(10.0),
        )
    except httpx.HTTPError as exc:
        raise AuthServerUnavailable("couldn't reach Supabase Auth") from exc


def generate_recovery_link(email: str) -> str:
    """
    A one-time "set a new password" link for this email, for the admin to
    pass on personally (the app has no email service of its own). Supabase
    only returns the link here — it doesn't send an email.
    """
    if not settings.supabase_url:
        raise AuthNotConfigured("SUPABASE_URL")
    headers = _admin_headers()   # raises AuthNotConfigured without a secret key
    response = _post_admin("/admin/generate_link", {"type": "recovery", "email": email}, headers)
    if response.status_code in (404, 422):
        raise NoSuchAuthUser(email)
    if response.status_code in (401, 403):
        raise AuthNotConfigured("a valid SUPABASE_SECRET_KEY (Supabase rejected it)")
    if response.status_code != 200:
        raise AuthServerUnavailable(f"Supabase Auth answered HTTP {response.status_code}")
    try:
        data = response.json()
    except ValueError as exc:
        raise AuthServerUnavailable("Supabase Auth sent an unreadable reply") from exc
    link = data.get("action_link") or (data.get("properties") or {}).get("action_link")
    if not link:
        raise AuthServerUnavailable("Supabase Auth didn't include a link")
    return link
