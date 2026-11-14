"""
Authentication for the invite-only friends beta — Supabase Auth edition.

Two layers, kept deliberately separate:

  1. *Who is calling?* Supabase answers that. The browser signs in with
     Supabase (email + password or Google) and sends the resulting access
     token as `Authorization: Bearer <token>` on every request;
     app/supabase_auth.py verifies it locally against the project's public
     keys.

  2. *Are they allowed in?* This app answers that, with its own `users`
     table, exactly as before: an invite code creates a 'pending' account,
     an admin approves it, and every query is scoped by `users.id`. A Supabase
     login on its own grants nothing.

The bridge between the two is `users.supabase_uid` (the token's `sub`). It's
filled in on a person's first signed-in request: an existing account whose
email matches the token's — and which has no Supabase login linked yet — gets
linked, but only once Supabase confirms that email is verified. That's how
pre-Supabase accounts (the admin, the first friends) carry over with all
their data and no manual migration step. A linked account is never re-linked
automatically; reconnecting one is an admin job.

Apple Health ingest (an iOS Shortcut / Health Auto Export, not a browser)
still authenticates with the per-user `ingest_token` — see
require_ingest_auth — since a Shortcut can't run a Supabase sign-in.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session as DBSession

from app import supabase_auth
from app.db import get_db
from app.models import User
from app.supabase_auth import Identity

# How stale users.last_login_at may get before a request refreshes it. It's
# the Admin page's "last seen" column — hourly precision is plenty, and it
# keeps most requests from writing to the database.
_LAST_SEEN_RESOLUTION = timedelta(hours=1)

_BEARER_CHALLENGE = {"WWW-Authenticate": "Bearer"}


@dataclass(frozen=True)
class SignedIn:
    """A verified Supabase sign-in, plus the raw token for follow-up calls."""
    identity: Identity
    token: str


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header[:7].lower() == "bearer ":
        return header[7:].strip() or None
    return None


def _service_unavailable(exc: Exception) -> HTTPException:
    if isinstance(exc, supabase_auth.AuthNotConfigured):
        return HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Login isn't configured on this server (missing {exc}).",
        )
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        "Couldn't reach the login service. Try again in a moment.",
    )


def require_signed_in(request: Request) -> SignedIn:
    """
    Dependency: a valid Supabase access token, whether or not the person has
    an account in this app yet. Used directly only by /join and /me; data
    routes use require_auth.
    """
    token = _bearer_token(request)
    if token is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                            headers=_BEARER_CHALLENGE)
    try:
        identity = supabase_auth.verify_access_token(token)
    except supabase_auth.InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid",
                            headers=_BEARER_CHALLENGE)
    except (supabase_auth.AuthNotConfigured, supabase_auth.AuthServerUnavailable) as exc:
        raise _service_unavailable(exc)
    return SignedIn(identity=identity, token=token)


def email_confirmed(signed_in: SignedIn) -> bool:
    """Ask Supabase whether this sign-in's email is verified (HTTP errors
    become a 503 for the caller)."""
    try:
        return supabase_auth.email_is_confirmed(signed_in.token)
    except supabase_auth.InvalidToken:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid",
                            headers=_BEARER_CHALLENGE)
    except (supabase_auth.AuthNotConfigured, supabase_auth.AuthServerUnavailable) as exc:
        raise _service_unavailable(exc)


def link_existing_account(db: DBSession, signed_in: SignedIn) -> User | None:
    """
    Attach this Supabase login to an existing, not-yet-linked account with
    the same email — only if Supabase confirms the email is verified.
    Returns the linked user, or None when there's nothing (safe) to link.
    """
    email = signed_in.identity.email
    if not email:
        return None
    user = (
        db.query(User)
        .filter(User.email == email, User.supabase_uid.is_(None))
        .first()
    )
    if user is None or not email_confirmed(signed_in):
        return None
    user.supabase_uid = signed_in.identity.uid
    db.commit()
    db.refresh(user)
    return user


def get_account(request: Request, db: DBSession = Depends(get_db)) -> User:
    """
    Dependency: the app account behind this sign-in, whatever its status
    (pending and disabled included — /me reports the status so the app can
    show "waiting for approval"). 403 "no_account" means a valid Supabase
    login with no app account: the frontend then asks for an invite code.
    """
    signed_in = require_signed_in(request)
    user = db.query(User).filter(User.supabase_uid == signed_in.identity.uid).first()
    if user is None:
        user = link_existing_account(db, signed_in)
    if user is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "no_account")
    return user


def require_auth(request: Request, db: DBSession = Depends(get_db)) -> User:
    """
    Dependency for every data route: the current, *active* user. Routers
    filter every query by its id. 401 = not signed in (or token expired);
    403 = signed in but not allowed in yet ("no_account",
    "pending_approval") or any more ("account_disabled").
    """
    user = get_account(request, db)
    if user.status == "pending":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "pending_approval")
    if user.status != "active":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account_disabled")

    now = datetime.utcnow()
    if user.last_login_at is None or now - user.last_login_at > _LAST_SEEN_RESOLUTION:
        user.last_login_at = now
        db.commit()
    return user


def require_admin(current_user: User = Depends(require_auth)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user


def require_ingest_auth(request: Request, db: DBSession = Depends(get_db)) -> User:
    """
    Bearer-token auth for the Apple Health Shortcut / Health Auto Export
    pushes — a non-browser client that can't run a Supabase sign-in.
    Completely separate from the Supabase login above: the bearer value here
    is the user's long-lived `ingest_token`, not an access token.
    """
    token = _bearer_token(request)
    if token is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
            headers=_BEARER_CHALLENGE,
        )
    user = db.query(User).filter(User.ingest_token == token).first()
    if user is None or user.status != "active":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid ingest token",
            headers=_BEARER_CHALLENGE,
        )
    return user
