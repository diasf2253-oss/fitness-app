"""
Auth endpoints (Phase 1-2 friends beta): invite-gated signup, login/logout,
"who am I", and the forced password-change escape hatch.

Every account starts 'pending' after /join and needs an admin approval
(see routers/admin.py) before it can log in. No email service in v1 — see
friends-beta-prompt-pack.md.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session as DBSession

from app.auth import (
    create_session,
    clear_session_cookie,
    hash_password,
    require_auth,
    set_session_cookie,
    verify_password,
)
from app.config import settings
from app.db import get_db
from app.models import AuthSession, InviteCode, User
from app.schemas import ChangePasswordRequest, JoinRequest, LoginRequest, UserMeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/join")
def join(body: JoinRequest, db: DBSession = Depends(get_db)):
    """
    Creates a 'pending' account if — and only if — `code` is a valid, active,
    not-yet-exhausted invite code. Enforced here at the API, not just hidden
    in the frontend: a request with no/invalid code can never create an
    account, full stop.
    """
    code = (
        db.query(InviteCode)
        .filter(InviteCode.code == body.code, InviteCode.active.is_(True))
        .first()
    )
    if code is None or (code.max_uses is not None and code.uses >= code.max_uses):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired invite code")

    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with that email already exists")

    user = User(
        email=email,
        password_hash=hash_password(body.password),
        name=body.name.strip(),
        status="pending",
    )
    db.add(user)
    code.uses += 1
    db.commit()
    return {"status": "pending"}


@router.post("/login")
def login(body: LoginRequest, response: Response, db: DBSession = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    # Same generic message for "no such user" and "wrong password" — avoid
    # leaking which emails have accounts.
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    if user.status == "pending":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "pending_approval")
    if user.status == "disabled":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "account_disabled")

    session_id, max_age = create_session(db, user, remember=body.remember)
    set_session_cookie(response, session_id, max_age)

    user.last_login_at = datetime.utcnow()
    db.commit()
    return {"status": "ok"}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Kills only the current device's session — other logged-in devices
    for this user are unaffected (that's what temp-password reset is for)."""
    session_id = request.cookies.get(settings.session_cookie_name)
    if session_id:
        db.query(AuthSession).filter(AuthSession.session_id == session_id).delete()
        db.commit()
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me", response_model=UserMeOut)
def me(current_user: User = Depends(require_auth)):
    """A 401 here is the normal logged-out state, not an error."""
    return current_user


@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Allowed even while must_change_password is set — this IS the escape
    hatch require_auth otherwise blocks everything behind. Invalidates
    every *other* session for this account (keeps the current tab logged
    in) — matters most right after an admin-issued temp password.
    """
    current_user.password_hash = hash_password(body.new_password)
    current_user.must_change_password = False

    current_session_id = request.cookies.get(settings.session_cookie_name)
    db.query(AuthSession).filter(
        AuthSession.user_id == current_user.id,
        AuthSession.session_id != current_session_id,
    ).delete(synchronize_session=False)

    db.commit()
    return {"status": "ok"}
