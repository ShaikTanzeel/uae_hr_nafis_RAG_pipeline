"""
seed.py — automatic account seeding (PHASE 3, Section C).

Per §4: there is no sign-up screen. Instead, one Admin and one demo HR User
account are created automatically the first time the app starts, from
credentials in .env. Call seed_users() once at app startup (Section F wires
this into FastAPI's startup event) — it's safe to call every time the app
starts, since it only acts when the `users` table is completely empty.
"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import hash_password
from src.config import settings
from src.models.user import User, UserRole


async def seed_users(db: AsyncSession) -> None:
    """Create the seed Admin + demo HR User accounts, but only if the `users`
    table is currently empty — running this on every startup must never create
    duplicates."""
    result = await db.execute(select(func.count()).select_from(User))
    user_count = result.scalar_one()

    if user_count > 0:
        return  # Already seeded (or real users exist) — do nothing.

    admin = User(
        email=settings.SEED_ADMIN_EMAIL,
        hashed_password=hash_password(settings.SEED_ADMIN_PASSWORD),
        role=UserRole.ADMIN,
        is_demo_account=True,
    )
    hr_user = User(
        email=settings.SEED_HR_EMAIL,
        hashed_password=hash_password(settings.SEED_HR_PASSWORD),
        role=UserRole.HR_USER,
        is_demo_account=True,
    )

    db.add_all([admin, hr_user])
    await db.commit()
