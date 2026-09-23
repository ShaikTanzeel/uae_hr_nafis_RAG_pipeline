"""
user.py — the `users` table (§3, Phase 3 Section B1).

One row per person who can log in. Columns beyond the basic email/password/role
from §3 are here because they belong to this same table and this phase's other
sections (C: demo-account seeding, H: login lockout) need them from day one —
adding them now avoids a second migration touching this table later.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class UserRole(str, enum.Enum):
    """Matches §4's two account types: Admin (manages everything) vs HR User
    (asks questions, sees only their own history)."""
    ADMIN = "admin"
    HR_USER = "hr_user"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    # values_callable forces the column to store the lowercase .value ("admin",
    # "hr_user") instead of SQLAlchemy's default of storing the Python member
    # NAME ("ADMIN", "HR_USER") — without this, the DB and the enum's own
    # values silently disagree, which matters once Section G compares role
    # strings from a decoded JWT against this column.
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Section C: protects the auto-seeded demo accounts from deletion/password
    # changes, regardless of DEMO_MODE's on/off display setting.
    is_demo_account: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Section H: brute-force login lockout (5 wrong attempts -> 15 min lock).
    failed_login_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
