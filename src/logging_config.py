"""
logging_config.py — Centralised Logging Setup for the UAE HR & Nafis Copilot

WHY THIS FILE EXISTS:
    In a production application, we need structured, reliable logs so we can:
    1. Filter events by request (using Trace IDs)
    2. Know the severity of each event (INFO, WARNING, ERROR)
    3. Record timestamps for every event
    4. Write logs to both the terminal AND a persistent log file

HOW TO USE IT IN OTHER FILES:
    from src.logging_config import get_logger
    logger = get_logger(__name__)       # __name__ = the file name e.g. "src.agent"

    logger.info("Agent started")        # General information
    logger.warning("Low confidence!")   # Something unexpected but not fatal
    logger.error("DB connection failed") # Something broke

TRACE IDs:
    A Trace ID is a unique token generated per request (e.g. "A3F7B91C").
    Every log from that request is stamped with the same ID, making it easy
    to reconstruct exactly what happened for a single user query.

    Use the context manager to set a Trace ID for the current request:

    with trace_context("A3F7B91C"):
        logger.info("Starting retrieval")   # -> logged with [A3F7B91C]
        logger.info("Calling LLM")          # -> logged with [A3F7B91C]
"""

import os
import logging
import uuid
from contextlib import contextmanager
from contextvars import ContextVar

# =============================================================================
# TRACE ID — per-request unique identifier
# =============================================================================
# ContextVar is a Python built-in that stores a value PER REQUEST,
# even if multiple requests are running at the same time.
# This is the correct way to do per-request state in a web server.
_trace_id_var: ContextVar[str] = ContextVar("trace_id", default="--------")


def get_trace_id() -> str:
    """Returns the current request's trace ID, or '--------' if not set."""
    return _trace_id_var.get()


def generate_trace_id() -> str:
    """Generates a short 8-character unique ID for a new request."""
    return str(uuid.uuid4())[:8].upper()


@contextmanager
def trace_context(trace_id: str = None):
    """
    Context manager that sets the Trace ID for all logs within its scope.

    Usage:
        trace_id = generate_trace_id()
        with trace_context(trace_id):
            logger.info("This will be logged with the trace ID")

    When the 'with' block exits, the trace ID is automatically cleaned up.
    """
    if trace_id is None:
        trace_id = generate_trace_id()
    token = _trace_id_var.set(trace_id)
    try:
        yield trace_id
    finally:
        _trace_id_var.reset(token)


# =============================================================================
# LOG FORMATTER — gives every log line a consistent, human-readable structure
# =============================================================================

class TraceIdFormatter(logging.Formatter):
    """
    Custom log formatter that injects the current Trace ID into every log line.

    Output format:
        2026-07-03 01:12:00 | INFO     | src.agent | [A3F7B91C] | Phase A: Retrieving laws...
        2026-07-03 01:12:01 | WARNING  | src.db    | [A3F7B91C] | Rate limit hit, retrying...
        2026-07-03 01:12:02 | ERROR    | src.db    | [A3F7B91C] | Qdrant connection failed!

    Columns explained:
        - Timestamp:  When exactly this happened
        - Level:      INFO (normal), WARNING (unexpected), ERROR (broken)
        - Module:     Which Python file generated this log (e.g. src.agent)
        - Trace ID:   Which user request this belongs to
        - Message:    The actual log message
    """
    def format(self, record: logging.LogRecord) -> str:
        record.trace_id = get_trace_id()
        return super().format(record)


# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

# Directory to store log files. We put them in a 'logs/' folder in the project root.
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)   # Create 'logs/' folder if it doesn't already exist
LOG_FILE = os.path.join(LOG_DIR, "copilot.log")

# The log format string. %(asctime)s etc. are Python logging placeholders.
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | [%(trace_id)s] | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def _is_configured() -> bool:
    """Checks if logging has already been set up to avoid duplicate handlers."""
    root_logger = logging.getLogger()
    return any(isinstance(h, (logging.StreamHandler, logging.FileHandler))
               for h in root_logger.handlers)


def configure_logging(level: int = logging.INFO):
    """
    Sets up the root logger with two output channels:
        1. Console (Terminal): So you see logs in real-time during development.
        2. File (logs/copilot.log): So logs are persisted on disk for later review.

    This should be called ONCE at application startup.
    Calling it multiple times is safe — it checks if it's already been configured.
    """
    if _is_configured():
        return  # Already configured, skip

    formatter = TraceIdFormatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # --- Handler 1: Console Output ---
    # Shows logs in your terminal window in real-time
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    root_logger.addHandler(console_handler)

    # --- Handler 2: File Output ---
    # Writes logs to logs/copilot.log on disk
    # mode='a' means "append" — new logs are added at the end, old ones kept
    file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    root_logger.addHandler(file_handler)

    # Silence overly-chatty third-party libraries
    # These generate hundreds of debug lines we don't care about
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger for a specific module.

    Usage:
        from src.logging_config import get_logger
        logger = get_logger(__name__)
        logger.info("Hello from this module!")

    Why use __name__?
        Python automatically sets __name__ to the module's full import path,
        e.g. "src.agent" or "src.database". This appears in the log line
        so you always know which file generated the log.
    """
    configure_logging()   # Ensure logging is configured (idempotent)
    return logging.getLogger(name)


# =============================================================================
# QUICK SELF-TEST — run this file directly to confirm logging is working
# python src/logging_config.py
# =============================================================================
if __name__ == "__main__":
    logger = get_logger(__name__)
    trace_id = generate_trace_id()

    print(f"\nRunning logging self-test with Trace ID: {trace_id}\n")

    with trace_context(trace_id):
        logger.info("Test 1: INFO log — normal system activity")
        logger.warning("Test 2: WARNING log — something unexpected, not fatal")
        logger.error("Test 3: ERROR log — something broke!")

    # After the context manager, trace ID is reset
    logger.info("Test 4: INFO log OUTSIDE trace context — trace_id should show '--------'")

    print(f"\nLog file written to: {LOG_FILE}")
