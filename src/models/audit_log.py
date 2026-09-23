"""
audit_log.py — the `audit_logs` table (§3, §7, Phase 3 Section B7).

A permanent, append-only record of who did what and when. `user_id` is
nullable because a failed login attempt may not resolve to a real user (e.g.
an email that doesn't exist).

APPEND-ONLY: no code anywhere in this project may UPDATE or DELETE a row in
this table — that's what makes it trustworthy as an audit trail rather than
just another table. This model intentionally has no `updated_at` column,
since a row is never expected to change after insert. The real enforcement of
this rule is a database-level permission grant (Section I2), not something a
Python class can guarantee by itself — a comment here is a signpost, not a
safeguard.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)  # 45 = max IPv6 length
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
