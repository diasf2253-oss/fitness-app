"""
Auth endpoints for the invite-only friends beta (Supabase Auth edition).

Signing in, signing out, password changes and resets all happen in the
browser against Supabase (see frontend/src/auth/auth.jsx) — there are no login or
password endpoints here any more. What's left is this app's own say over who
gets in:

  - POST /join  — a signed-in Supabase user with no app account redeems an
                  invite code; the account starts 'pending' until an admin
                  approves it (routers/admin.py).
  - GET  /me    — who am I, including a pending/disabled status.
  - PATCH /me   — rename.
  - POST /ingest-token/rotate — new Apple Health ingest credential.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session as DBSession

from app.core.auth import (
    SignedIn,
    email_confirmed,
    get_account,
    link_existing_account,
    require_auth,
    require_signed_in,
)
from app.core.db import get_db
from app.core.ratelimit import rate_limit
from app.models import InviteCode, User, _new_ingest_token
from app.schemas import JoinRequest, UpdateMeRequest, UserMeOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/join", dependencies=[Depends(rate_limit(5, scope="join"))])
def join(
    body: JoinRequest,
    signed_in: SignedIn = Depends(require_signed_in),
    db: DBSession = Depends(get_db),
):
    """
    Turn a Supabase sign-in into a 'pending' app account, if — and only if —
    `code` is a valid, active, not-yet-exhausted invite code. Enforced here
    at the API, not just in the UI: a valid Supabase login alone can never
    create an account.

    Idempotent for someone who already has an account (returns its status),
    and an existing account with this email that has no Supabase login yet
    is simply linked — no invite needed to get your own data back.
    """
    identity = signed_in.identity

    existing = db.query(User).filter(User.supabase_uid == identity.uid).first()
    if existing is not None:
        return {"status": existing.status}

    if not identity.email:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Your login has no email address, which this app needs.")

    by_email = db.query(User).filter(User.email == identity.email).first()
    if by_email is not None:
        if by_email.supabase_uid is not None:
            # Linked to a different Supabase login — reconnecting is an admin job.
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An account with that email already exists")
        linked = link_existing_account(db, signed_in)
        if linked is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                "Confirm your email address first, then try again.")
        return {"status": linked.status}

    code = (
        db.query(InviteCode)
        .filter(InviteCode.code == body.code.strip(), InviteCode.active.is_(True))
        .first()
    )
    if code is None or (code.max_uses is not None and code.uses >= code.max_uses):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired invite code")

    name = body.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name can't be empty.")

    # Only a verified address may claim an account: otherwise someone could
    # sign up as friend@example.com without owning it and squat that email.
    if not email_confirmed(signed_in):
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Confirm your email address first, then try again.")

    db.add(User(
        email=identity.email,
        supabase_uid=identity.uid,
        name=name,
        status="pending",
    ))
    code.uses += 1
    db.commit()
    return {"status": "pending"}


@router.get("/me", response_model=UserMeOut)
def me(current_user: User = Depends(get_account)):
    """
    Who's signed in — answered for pending and disabled accounts too, so
    the app can show the right screen. A 401 here is the normal signed-out
    state; a 403 "no_account" means "signed in with Supabase, but hasn't
    joined with an invite code yet".
    """
    return current_user


@router.patch("/me", response_model=UserMeOut)
def update_me(
    body: UpdateMeRequest,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """Change the display name (the email is the Supabase login — it's
    changed there, not here)."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name can't be empty.")
    current_user.name = name
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/ingest-token/rotate", response_model=UserMeOut)
def rotate_ingest_token(
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    """
    Issue a fresh Apple Health ingest token, invalidating the old one.

    The ingest token is a long-lived bearer credential that gets pasted into
    an iOS Shortcut (a Shortcut can't run a Supabase sign-in), so it travels
    further than a login does — into screenshots, shared setup notes, a
    Shortcut someone re-shares. Rotating breaks any Shortcut still holding
    the old value, which is the point.
    """
    current_user.ingest_token = _new_ingest_token()
    db.commit()
    db.refresh(current_user)
    return current_user
