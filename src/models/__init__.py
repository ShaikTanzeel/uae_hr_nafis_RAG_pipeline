"""
src/models — one file per database table (SQLAlchemy ORM models), per §3.

Every model file must be imported here so its table registers on
Base.metadata before Alembic's autogenerate compares against it — a model
that exists as a Python file but was never imported is invisible to Alembic.
"""

from src.models.user import User  # noqa: F401
from src.models.conversation import Conversation  # noqa: F401
from src.models.message import Message  # noqa: F401
from src.models.document import Document  # noqa: F401
from src.models.document_article import DocumentArticle  # noqa: F401
from src.models.ingestion_job import IngestionJob  # noqa: F401
from src.models.audit_log import AuditLog  # noqa: F401
from src.models.app_setting import AppSetting  # noqa: F401
from src.models.refresh_token import RefreshToken  # noqa: F401
