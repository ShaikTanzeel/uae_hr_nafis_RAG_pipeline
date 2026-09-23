"""
tokens.py — JWT access tokens (PHASE 3, Section E).

An access token is a signed, tamper-proof "wristband": it lets every request
prove who's asking (user_id, role) and until when (exp), without the server
touching the database on every single request. It's deliberately short-lived
(30 minutes) — see Section E3/refresh_token.py for how a session survives
past that without forcing a re-login.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.refresh_token import RefreshToken

ACCESS_TOKEN_LIFETIME = timedelta(minutes=30)
REFRESH_TOKEN_LIFETIME = timedelta(days=7)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Build and sign a JWT encoding who this user is and until when this
    token is valid. Signed with JWT_SECRET — anyone without that secret can
    read the contents (JWTs are not encrypted) but cannot forge a valid one."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),  # "sub" (subject) is the standard JWT claim for "who this token is about"
        "role": role,
        "iat": now,  # issued-at
        "exp": now + ACCESS_TOKEN_LIFETIME,  # expiry — the whole point of a *short-lived* token
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """Verify a token's signature and expiry, and return its payload.
    Raises jwt.InvalidTokenError (or a subclass, e.g. jwt.ExpiredSignatureError)
    if the token is invalid, expired, or was signed with a different secret —
    callers (Section G) turn that into an HTTP 401, not a silent pass-through.
    """
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def _hash_refresh_token(raw_token: str) -> str:
    """SHA-256 hex digest of a raw refresh token. Unlike password hashing,
    this does not need Argon2's slow, salted design — a refresh token is
    already a long random value (not a human-memorable password an attacker
    could dictionary-guess), so a fast, deterministic hash is fine, and being
    deterministic is required here anyway (Section F needs to look a presented
    token up by its hash)."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


async def create_refresh_token(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Generate a new refresh token, store only its hash in the database, and
    return the raw token — this raw value is only ever available here, at
    creation time; it cannot be recovered from the database afterward."""
    raw_token = secrets.token_urlsafe(32)
    row = RefreshToken(
        user_id=user_id,
        token_hash=_hash_refresh_token(raw_token),
        expires_at=datetime.now(timezone.utc) + REFRESH_TOKEN_LIFETIME,
    )
    db.add(row)
    await db.commit()
    return raw_token


async def revoke_refresh_token(db: AsyncSession, raw_token: str) -> None:
    """Used by logout (Section F2): marks a refresh token revoked without
    issuing a replacement. Silently does nothing if the token doesn't match
    any row or is already revoked — logout should never fail just because the
    cookie was already stale."""
    token_hash = _hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        await db.commit()


async def revoke_all_refresh_tokens(db: AsyncSession, user_id: uuid.UUID) -> None:
    """Revoke every currently-active refresh token for a user in one go. Used
    by: E3's reuse-detection (a stolen token was replayed — kill every
    session), and F4's change-password (an old session, possibly on a device
    that no longer has the current password, must not be able to linger)."""
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await db.commit()


class RefreshTokenError(Exception):
    """Raised when a presented refresh token is invalid, expired, or already
    used. Section F's /api/auth/refresh route catches this and responds with
    a generic 401 — the caller must log in again either way, so there's no
    need (and no safe way) to tell them exactly which case it was."""
    pass


async def rotate_refresh_token(db: AsyncSession, raw_token: str) -> tuple[str, uuid.UUID]:
    """Validate a presented refresh token and, if valid, retire it and issue a
    brand new one — this is what lets a session survive past the 30-minute
    access token without asking for a password again.

    Returns (new_raw_token, user_id) on success.

    Reuse detection: if the presented token matches a row that's already
    revoked, that means this exact token was already rotated away once before
    — a legitimate browser would never present it again, since it always
    switches to the newest token. Seeing it again means it was copied
    somewhere (stolen) and is now being replayed. The response is to assume
    that user's session is compromised and revoke ALL of their refresh
    tokens, forcing a real re-login everywhere.
    """
    token_hash = _hash_refresh_token(raw_token)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    row = result.scalar_one_or_none()

    if row is None:
        raise RefreshTokenError("Refresh token not recognized.")

    if row.revoked_at is not None:
        # Reuse of an already-retired token — treat as theft, nuke every
        # active session for this user.
        await revoke_all_refresh_tokens(db, row.user_id)
        raise RefreshTokenError("Refresh token reuse detected — all sessions revoked.")

    if row.expires_at < datetime.now(timezone.utc):
        raise RefreshTokenError("Refresh token expired.")

    row.revoked_at = datetime.now(timezone.utc)
    new_raw_token = await create_refresh_token(db, row.user_id)
    await db.commit()
    return new_raw_token, row.user_id
