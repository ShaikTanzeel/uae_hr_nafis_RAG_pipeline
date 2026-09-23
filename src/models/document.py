"""
document.py — the `documents` table (§3, Phase 3 Section B4).

One row per uploaded law PDF: title, whether it's enabled, article count,
processing status. Populated for real starting Phase 4 (Document Library);
the table exists now so later phases are additive, not schema-breaking.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    article_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # "queued" | "processing" | "done" | "failed" — plain string, not a DB enum,
    # since Phase 4 (ingestion_jobs, Section B6) is where this vocabulary is
    # actually exercised and may need new statuses without a migration.
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="done")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
