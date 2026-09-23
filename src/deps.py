"""
deps.py — FastAPI dependencies for authentication (PHASE 3, Sections G1/G2).

A FastAPI "dependency" is a function the route declares as a parameter;
FastAPI runs it before the route body and passes its return value in. Using
one for auth means every protected route gets the same identity check by
declaring `user: User = Depends(get_current_user)` — the check can't be
forgotten in one route and not another, since it's not copy-pasted logic.
"""

import uuid

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.models.user import User, UserRole
from src.tokens import decode_access_token


async def get_current_user(
    access_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Reads the access_token cookie, verifies it, and loads the real user
    row. Raises 401 for anything wrong — no cookie, bad signature, expired,
    or a user id that no longer exists (e.g. deleted after the token was
    issued)."""
    if access_token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = decode_access_token(access_token)
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    """Wraps get_current_user with a role check. 403 (Forbidden), not 401
    (Unauthorized) — the caller IS authenticated, they're just not allowed to
    do this specific thing. Every admin-only route (this phase and later
    phases: documents, settings, users, audit) must depend on this, not on a
    frontend check — a hidden button is not a security control, since anyone
    can still call the underlying route directly."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")
    return user
