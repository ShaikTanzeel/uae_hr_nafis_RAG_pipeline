"""
message.py — the `messages` table (§3, Phase 3 Section B3).

One row per question or answer in a conversation, including citations,
reasoning steps, and confidence. Populated for real starting Phase 5; the
table exists now so later phases are additive, not schema-breaking.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(String, nullable=False)

    # JSON columns — matches Phase 2's AgentResponse shape (src/schemas.py):
    # citations, reasoning steps, and confidence are already structured data
    # produced by the pipeline, not something this table needs to normalize
    # into more tables.
    citations: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reasoning_steps: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
