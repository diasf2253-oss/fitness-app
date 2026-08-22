"""
Admin endpoints (Phase 1-2 friends beta): pending-signup approval, user
management, and admin-issued temp passwords. User-management scope only —
no drill-down into any user's actual fitness data.
"""
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.auth import hash_password, require_admin
from app.db import get_db
from app.models import AuthSession, InviteCode, User
from app.schemas import (
    AdminUserOut,
    InviteCodeCreate,
    InviteCodeOut,
    TempPasswordOut,
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
def reject_user(user_id: int, db: DBSession = Depends(get_db), _: User = Depends(require_admin)):
    """Soft-disable, not delete — preserves the invite code's use count and
    the account as an audit trail. Same effect as later disabling them."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
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


@router.post("/users/{user_id}/temp-password", response_model=TempPasswordOut)
def issue_temp_password(
    user_id: int, db: DBSession = Depends(get_db), _: User = Depends(require_admin)
):
    """Generates a one-time temp password, shown to the admin exactly once
    in the response — never logged or stored in plaintext. Forces a change
    on next login and kills every existing session for that account."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    temp_password = secrets.token_urlsafe(9)
    user.password_hash = hash_password(temp_password)
    user.must_change_password = True
    db.query(AuthSession).filter(AuthSession.user_id == user.id).delete(synchronize_session=False)
    db.commit()
    return TempPasswordOut(temp_password=temp_password)


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
