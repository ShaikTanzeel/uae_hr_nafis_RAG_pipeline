"""
refresh_token.py — the `refresh_tokens` table (PHASE 3, Section E2).

The refresh token handed to the browser is only ever seen once, at issue time.
The database stores a HASH of it, not the token itself — same reasoning as
password hashing (src/auth.py): if the database ever leaked, an attacker
would get unusable hashes, not live sessions they could replay.

`revoked_at` is what makes rotation (Section E3) and logout possible: a token
row is never deleted, only marked revoked, so "was this token used already?"
(the reuse-detection check) stays answerable after the fact.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    # SHA-256 hex digest is always 64 characters — see src/tokens.py's hashing helper.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
