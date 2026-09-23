"""
audit.py — writing to the audit log (PHASE 3, Section I).

This is the ONLY function in the project that should ever construct an
AuditLog row. Centralizing it here (rather than each route inserting its own
row) means every audit entry has the same shape, and makes "does anything in
this codebase update or delete an audit_logs row" a one-file question to
answer, not a project-wide grep.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from src.models.audit_log import AuditLog


async def log_audit_event(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    """Insert one row into audit_logs. Pure insert — nothing in this function
    (or anything that calls it) may UPDATE or DELETE an existing row; that's
    what makes the table trustworthy as a record of what actually happened.

    user_id is optional because some events (e.g. a failed login against an
    email that doesn't exist) can't be tied to a real user row.
    """
    row = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=ip_address,
    )
    db.add(row)
    await db.commit()
