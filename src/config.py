"""
config.py — Single source of truth for all settings.

Loads once from `.env` (project root) into a validated Settings object.
Import `settings` from this module instead of calling os.getenv(...) directly.
"""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ENV_FILE = os.path.join(_PROJECT_ROOT, ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_ENV_FILE, extra="ignore")

    # --- AI providers ---
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Claude models — Phase 1 uses Haiku 4.5 for both main answer and query rewrite.
    # PHASE 2 — TASK C0: kept here (not deleted) as a reversible backup now that
    # the pipeline runs on Gemini instead — see GEMINI_CHAT_MODEL below.
    ANTHROPIC_MAIN_MODEL: str = "claude-haiku-4-5-20251001"
    ANTHROPIC_REWRITE_MODEL: str = "claude-haiku-4-5-20251001"

    # PHASE 2 — TASK C0: Gemini models for both main answer-writing and the
    # cheap query-rewrite/citation-extraction calls, replacing the Claude
    # models above. GEMINI_API_KEY already existed for embeddings (gemini-
    # embedding-001); these are separate settings for the chat/generation
    # models used by src/agent.py.
    GEMINI_CHAT_MODEL: str = "gemini-3.8-flash"
    GEMINI_REWRITE_MODEL: str = "gemini-3.8-flash"

    # --- Qdrant (vector search) ---
    QDRANT_URL: str = "http://localhost:6333"
    COLLECTION_ALIAS: str = "uae_hr_laws"

    # --- CORS ---
    CORS_ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- Postgres (PHASE 3) ---
    # POSTGRES_USER/PASSWORD/DB already existed from Phase 1 (they configure the
    # Docker container in docker-compose.yml — this is the SUPERUSER Postgres
    # creates on first startup). HOST/PORT are new: 5434 matches
    # docker-compose.yml's host-side port mapping (5433 was tried first but
    # collided with a native Postgres install on this machine — see the port
    # comment in docker-compose.yml).
    POSTGRES_USER: str = "uae_hr"
    POSTGRES_PASSWORD: str = "uae_hr"
    POSTGRES_DB: str = "uae_hr"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5434

    # PHASE 3 — Section I2: the app itself connects as a SEPARATE, restricted
    # role (not the superuser above), which only has SELECT+INSERT on
    # audit_logs (no UPDATE/DELETE) — the actual database-level enforcement of
    # "the audit trail is append-only," since privilege grants mean nothing
    # against a superuser connection. The superuser above is used ONLY by
    # Alembic (alembic/env.py), which legitimately needs to CREATE/ALTER
    # tables — a power the restricted app role deliberately does not have.
    APP_DB_USER: str = "uae_hr_app"
    APP_DB_PASSWORD: str = ""

    @property
    def DATABASE_URL(self) -> str:
        """The connection string the APPLICATION uses at runtime — via the
        restricted APP_DB_USER role, never the superuser."""
        return (
            f"postgresql+asyncpg://{self.APP_DB_USER}:{self.APP_DB_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def MIGRATION_DATABASE_URL(self) -> str:
        """The connection string ALEMBIC uses — via the Postgres superuser,
        since migrations need to create/alter tables, a power the restricted
        app role intentionally does not have."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # --- Auth (PHASE 3) ---
    # No default for JWT_SECRET on purpose — see the __init__ check below. A
    # missing secret must fail loudly at startup, never silently fall back to a
    # guessable value that would let anyone forge a valid login token.
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"

    # --- Seed accounts (PHASE 3, Section C) ---
    # No defaults for the passwords, same reasoning as JWT_SECRET — a shipped
    # default password is a guessable password. Whoever sets up the project
    # must choose real values in .env.
    SEED_ADMIN_EMAIL: str = "admin@uae-hr.local"
    SEED_ADMIN_PASSWORD: str = ""
    SEED_HR_EMAIL: str = "hr.user@uae-hr.local"
    SEED_HR_PASSWORD: str = ""

    # Cosmetic only (§4): controls whether the future login page is allowed to
    # display "try these test credentials." Does NOT affect whether the seeded
    # accounts exist or work — see Section C4 for the actual protection logic.
    DEMO_MODE: bool = True

    # Controls the cookie's `Secure` flag (Section E4): when true, browsers
    # will only ever send the cookie over HTTPS. Defaults to False so local
    # HTTP development works; must be set true in any real deployment, where
    # traffic runs over HTTPS.
    COOKIE_SECURE: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.JWT_SECRET:
            raise ValueError(
                "JWT_SECRET is not set. Add JWT_SECRET=<a long random string> to your "
                ".env file — the app cannot sign login tokens without it."
            )
        if not self.SEED_ADMIN_PASSWORD or not self.SEED_HR_PASSWORD:
            raise ValueError(
                "SEED_ADMIN_PASSWORD and SEED_HR_PASSWORD must both be set in .env — "
                "these are the passwords for the two accounts created on first startup."
            )
        if not self.APP_DB_PASSWORD:
            raise ValueError(
                "APP_DB_PASSWORD is not set. This is the password for the restricted "
                "'uae_hr_app' Postgres role the application connects as (see Section I2) — "
                "it must be set in .env."
            )


settings = Settings()
