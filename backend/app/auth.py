"""
Session-cookie authentication for the multi-user friends beta.

Login creates an AuthSession row keyed by an opaque session id (never a
JWT — a DB-backed session lets logout and admin-issued temp-password resets
invalidate it server-side, which a stateless token can't do without a
blocklist table anyway). The id travels in an httpOnly, Secure, SameSite=Lax
cookie. Apple Health ingest (a Shortcut/HAE automation, not a browser)
authenticates separately via a per-user bearer `ingest_token` — see
require_ingest_auth — since a Shortcut can't hold a cookie jar.
"""
import secrets
from datetime import datetime, timedelta
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as DBSession

from app.config import settings
from app.db import get_db
from app.models import AuthSession, User

_hasher = PasswordHasher()

# Routes still reachable while a user's must_change_password flag is set —
# everything else 403s until they set a new password (see require_auth).
_PASSWORD_CHANGE_EXEMPT_PATHS = {
    "/api/auth/change-password",
    "/api/auth/logout",
    "/api/auth/me",
}


def hash_password(raw: str) -> str:
    return _hasher.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, raw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_session(db: DBSession, user: User, remember: bool) -> tuple[str, Optional[int]]:
    """
    Creates an AuthSession row and returns (session_id, cookie_max_age).
    cookie_max_age is None for a browser-session cookie ("stay signed in"
    unchecked — dies when the browser closes); otherwise
    session_max_age_days in seconds. The server-side row always expires
    after session_max_age_days regardless — only the cookie's own Max-Age
    (and therefore how long the browser keeps offering it back) differs.
    """
    session_id = secrets.token_urlsafe(32)
    max_age = settings.session_max_age_days * 86400 if remember else None
    expires_at = datetime.utcnow() + timedelta(days=settings.session_max_age_days)
    db.add(AuthSession(session_id=session_id, user_id=user.id, expires_at=expires_at))
    db.commit()
    return session_id, max_age


def set_session_cookie(response: Response, session_id: str, max_age: Optional[int]) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=max_age,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=settings.session_cookie_name, path="/")


def require_auth(request: Request, db: DBSession = Depends(get_db)) -> User:
    """
    Dependency that resolves the current User from the session cookie.
    Raises 401 if there's no cookie, the session is unknown/expired, or the
    account isn't active (pending/disabled users can't use the API either).
    Also enforces a pending must_change_password reset: every route 403s
    except the small exempt set above, until the user sets a new password.
    """
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    auth_session = (
        db.query(AuthSession)
        .filter(
            AuthSession.session_id == session_id,
            AuthSession.expires_at > datetime.utcnow(),
        )
        .first()
    )
    if auth_session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")

    user = db.get(User, auth_session.user_id)
    if user is None or user.status != "active":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")

    auth_session.last_seen_at = datetime.utcnow()
    db.commit()

    if user.must_change_password and request.url.path not in _PASSWORD_CHANGE_EXEMPT_PATHS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Password change required before continuing"
        )

    return user


def require_admin(current_user: User = Depends(require_auth)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user


def require_ingest_auth(request: Request, db: DBSession = Depends(get_db)) -> User:
    """
    Bearer-token auth for the Apple Health Shortcut / Health Auto Export
    pushes — a non-browser client that can't hold a cookie jar. Completely
    separate from the cookie session mechanism above.
    """
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header[7:].strip()
    user = db.query(User).filter(User.ingest_token == token).first()
    if user is None or user.status != "active":
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Invalid ingest token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
