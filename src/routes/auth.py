"""
routes/auth.py — login, logout, refresh, "who am I", and change-password
(PHASE 3, Section F), plus login lockout (PHASE 3, Section H).
"""

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.audit import log_audit_event
from src.auth import DemoAccountProtectedError, assert_not_demo_account, hash_password, verify_password
from src.config import settings
from src.db import get_db
from src.deps import get_current_user
from src.models.user import User
from src.tokens import (
    ACCESS_TOKEN_LIFETIME,
    REFRESH_TOKEN_LIFETIME,
    RefreshTokenError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    rotate_refresh_token,
)

MIN_PASSWORD_LENGTH = 12

# Section H: 5 wrong password attempts in a row locks the account for 15
# minutes (§4). Both numbers live here, not scattered as magic numbers in the
# route body below.
MAX_FAILED_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Section E4: cookie flags shared by every place a cookie gets set, so they
# can't silently drift apart between login and refresh.
_COOKIE_KWARGS = dict(
    httponly=True,      # JavaScript in the browser cannot read this cookie at all
    secure=settings.COOKIE_SECURE,  # only sent over HTTPS when true (see config.py)
    samesite="lax",     # not sent on most cross-site requests — the core CSRF defense here
)


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    response.set_cookie(
        "access_token", access_token,
        max_age=int(ACCESS_TOKEN_LIFETIME.total_seconds()),
        **_COOKIE_KWARGS,
    )
    response.set_cookie(
        "refresh_token", refresh_token,
        max_age=int(REFRESH_TOKEN_LIFETIME.total_seconds()),
        **_COOKIE_KWARGS,
    )


class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: str
    email: str
    role: str


_GENERIC_LOGIN_ERROR = "Invalid email or password."


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """F1 + Section H: verifies credentials, enforces the 5-attempt/15-minute
    lockout, and issues both tokens on success. Deliberately returns the exact
    same generic error in every failure case — wrong password, nonexistent
    email, AND a currently-locked account (§4) — so an attacker learns nothing
    about which case they hit, including whether the account even exists or
    is locked."""
    ip_address = request.client.host if request.client else None

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)

    # H2: a locked account is rejected even with the CORRECT password —
    # otherwise the lockout would be cosmetic. Checked before verify_password
    # so a correct password during lockout doesn't leak "you were right, but—".
    if user is not None and user.locked_until is not None and user.locked_until > now:
        await log_audit_event(
            db, "login_blocked_locked", user_id=user.id,
            details={"email": body.email}, ip_address=ip_address,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    if user is None or not verify_password(body.password, user.hashed_password) or not user.is_active:
        if user is not None and user.is_active:
            user.failed_login_attempts += 1
            locked_now = user.failed_login_attempts >= MAX_FAILED_LOGIN_ATTEMPTS
            if locked_now:
                user.locked_until = now + LOCKOUT_DURATION
            await db.commit()
            # I3: the audit trail records the real reason internally, even
            # though the user-facing error stays generic (H3) either way.
            await log_audit_event(
                db, "login_failed", user_id=user.id,
                details={"reason": "wrong_password", "locked_out": locked_now},
                ip_address=ip_address,
            )
        else:
            await log_audit_event(
                db, "login_failed", details={"email": body.email, "reason": "no_such_account_or_inactive"},
                ip_address=ip_address,
            )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_GENERIC_LOGIN_ERROR)

    # Successful login: clear any prior failed attempts / lockout.
    user.failed_login_attempts = 0
    user.locked_until = None
    await db.commit()
    await log_audit_event(db, "login_success", user_id=user.id, ip_address=ip_address)

    access_token = create_access_token(user.id, user.role.value)
    refresh_token = await create_refresh_token(db, user.id)
    _set_auth_cookies(response, access_token, refresh_token)

    return UserOut(id=str(user.id), email=user.email, role=user.role.value)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """F2: revokes the refresh token server-side (not just clearing cookies
    client-side) — a leaked refresh token must stop working the moment the
    real user logs out, not stay valid until it naturally expires."""
    if refresh_token is not None:
        await revoke_refresh_token(db, refresh_token)

    # I4: best-effort — logout still succeeds even with no valid access
    # token cookie (e.g. it already expired), so identity here is optional.
    user_id = None
    access_token = request.cookies.get("access_token")
    if access_token is not None:
        try:
            payload = decode_access_token(access_token)
            user_id = uuid.UUID(payload["sub"])
        except jwt.InvalidTokenError:
            pass
    ip_address = request.client.host if request.client else None
    await log_audit_event(db, "logout", user_id=user_id, ip_address=ip_address)

    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


@router.post("/refresh")
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """F3: applies E3's rotation — issues a fresh access + refresh token pair
    from a still-valid refresh token, without requiring the password again."""
    if refresh_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        new_refresh_token, user_id = await rotate_refresh_token(db, refresh_token)
    except RefreshTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one()

    new_access_token = create_access_token(user.id, user.role.value)
    _set_auth_cookies(response, new_access_token, new_refresh_token)

    return {"status": "ok"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    """F5: lets the frontend ask 'who am I' without decoding the cookie itself."""
    return UserOut(id=str(user.id), email=user.email, role=user.role.value)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """F4: requires the current password, enforces a minimum length on the
    new one, refuses on a protected demo account (§4 — those accounts must
    survive being poked at during a demo), and revokes every other active
    session once the password changes, so a session started under the old
    password can't keep working indefinitely."""
    ip_address = request.client.host if request.client else None

    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Current password is incorrect.")

    if len(body.new_password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"New password must be at least {MIN_PASSWORD_LENGTH} characters.",
        )

    try:
        assert_not_demo_account(user)
    except DemoAccountProtectedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    user.hashed_password = hash_password(body.new_password)
    await revoke_all_refresh_tokens(db, user.id)
    await db.commit()
    await log_audit_event(db, "password_changed", user_id=user.id, ip_address=ip_address)
