"""
db.py — SQLAlchemy async engine + session setup (PHASE 3).

Import `Base` from this module for every ORM model (Section B's tables will
subclass it). Import `get_db` as a FastAPI dependency in route functions that
need database access — it opens one session per request and always closes it,
even if the request raises an error.
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.config import settings

# The engine manages a pool of real network connections to Postgres. It's
# created once, when this module is first imported, and reused for the life
# of the running app — opening a brand new connection per query would be slow.
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# A session factory: calling this creates one new session (a single unit-of-work
# talking to the database), borrowing a connection from the engine's pool.
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    """Base class every ORM table model (Section B) will inherit from."""
    pass


async def get_db():
    """
    FastAPI dependency — yields one database session per request.

    Using `yield` (not `return`) means: the code after the `yield` always runs
    once the request is done, whether it succeeded or raised an exception —
    that's what guarantees the session gets closed and the connection goes
    back to the pool instead of leaking.
    """
    async with async_session_factory() as session:
        yield session
