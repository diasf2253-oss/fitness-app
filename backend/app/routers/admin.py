"""
Admin endpoints (Phase 1-2 friends beta): pending-signup approval, user
management, password-reset links and invite codes. User-management scope only — no
drill-down into any user's actual fitness data.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.core import supabase_auth
from app.core.auth import require_admin
from app.core.db import get_db
from app.models import InviteCode, User
from app.schemas import (
    AdminUserOut,
    InviteCodeCreate,
    InviteCodeOut,
    InviteCodeUpdate,
    ResetLinkOut,
    UserStatusUpdate,
)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/pending", response_model=list[AdminUserOut])
def list_pending(db: DBSession = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).filter(User.status == "pending").order_by(User.created_at).all()


@router.post("/users/{user_id}/approve", response_model=AdminUserOut)
def approve_user(user_id: int, db: DBSession = Depends(get_db), _: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    user.status = "active"
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reject", response_model=AdminUserOut)
def reject_user(
    user_id: int, db: DBSession = Depends(get_db), current_admin: User = Depends(require_admin)
):
    """Soft-disable, not delete — preserves the invite code's use count and
    the account as an audit trail. Same effect as later disabling them."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current_admin.id:
        # Same guard as update_user: rejecting yourself would lock the only
        # way back in (the Admin page) behind account_disabled.
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Cannot demote or disable your own admin account")
    user.status = "disabled"
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[AdminUserOut])
def list_users(db: DBSession = Depends(get_db), _: User = Depends(require_admin)):
    return db.query(User).order_by(User.created_at).all()


@router.patch("/users/{user_id}", response_model=AdminUserOut)
def update_user(
    user_id: int,
    body: UserStatusUpdate,
    db: DBSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.id == current_admin.id and (
        (body.role is not None and body.role != "admin")
        or (body.status is not None and body.status != "active")
    ):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Cannot demote or disable your own admin account",
        )
    if body.status is not None:
        user.status = body.status
    if body.role is not None:
        user.role = body.role
    db.commit()
    db.refresh(user)
    return user


@router.post("/users/{user_id}/reset-link", response_model=ResetLinkOut)
def password_reset_link(
    user_id: int, db: DBSession = Depends(get_db), _: User = Depends(require_admin)
):
    """
    A one-time "set a new password" link for this person, made by Supabase
    and shown to the admin to pass on personally (WhatsApp, in person) —
    the app sends no email itself. Opening it signs them in and asks for a
    new password. People can also reset on their own from the login screen
    ("Forgot password?"), which emails them; this is the fallback when that
    email doesn't arrive. Needs SUPABASE_SECRET_KEY on the server.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if user.supabase_uid is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{user.email} hasn't signed in with the new login yet, so there's no "
            "password to reset. Ask them to create their login with this email "
            "(or use Continue with Google) — their data links automatically.",
        )
    try:
        link = supabase_auth.generate_recovery_link(user.email)
    except supabase_auth.AuthNotConfigured as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE,
                            f"Reset links need {exc} on the server.")
    except supabase_auth.NoSuchAuthUser:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Supabase has no login for {user.email}.")
    except supabase_auth.AuthServerUnavailable:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY,
                            "Supabase didn't return a link — try again in a moment.")
    return ResetLinkOut(email=user.email, action_link=link)


@router.post("/invite-codes", response_model=InviteCodeOut)
def create_invite_code(
    body: InviteCodeCreate, db: DBSession = Depends(get_db), _: User = Depends(require_admin)
):
    code = InviteCode(
        code=secrets.token_urlsafe(9),
        label=body.label,
        max_uses=body.max_uses,
    )
    db.add(code)
    db.commit()
    db.refresh(code)
    return code


@router.get("/invite-codes", response_model=list[InviteCodeOut])
def list_invite_codes(db: DBSession = Depends(get_db), _: User = Depends(require_admin)):
    """Every invite code, newest first — active ones and switched-off ones."""
    return db.query(InviteCode).order_by(InviteCode.created_at.desc(), InviteCode.id.desc()).all()


@router.patch("/invite-codes/{code_id}", response_model=InviteCodeOut)
def update_invite_code(
    code_id: int,
    body: InviteCodeUpdate,
    db: DBSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Switch a code off (or back on). Codes are never deleted, so the record
    of who joined with which code stays intact."""
    code = db.get(InviteCode, code_id)
    if code is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite code not found")
    code.active = body.active
    db.commit()
    db.refresh(code)
    return code
