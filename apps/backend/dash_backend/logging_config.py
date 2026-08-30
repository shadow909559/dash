"""Structured logging configuration for the DASH backend."""

import logging
import os
import re
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Dict, Literal, Optional

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Log directory relative to the backend package root.
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "..", "..", "logs")
LOG_DIR = os.path.abspath(LOG_DIR)
CRASH_DIR = os.path.join(LOG_DIR, "crash")

# Per-component rotating log files.
COMPONENT_LOGS: Dict[str, str] = {
    "backend": "backend.log",
    "voice": "voice.log",
    "automation": "automation.log",
    "agents": "agents.log",
    "android": "android.log",
    "system": "system.log",
}

# Maximum file size per log (5 MB) and backup count (5).
MAX_LOG_BYTES = 5 * 1024 * 1024
BACKUP_COUNT = 5

# Patterns to redact from logs
SENSITIVE_PATTERNS = [
    (r'password["\s:=]+[^\s"\',}]+', 'password=***REDACTED***'),
    (r'token["\s:=]+[^\s"\',}]{20,}', 'token=***REDACTED***'),
    (r'api_key["\s:=]+[^\s"\',}]{20,}', 'api_key=***REDACTED***'),
    (r'secret["\s:=]+[^\s"\',}]{20,}', 'secret=***REDACTED***'),
    (r'Bearer\s+[A-Za-z0-9\-._~+/]+', 'Bearer ***REDACTED***'),
    (r'[a-f0-9]{32}', '***HASH_REDACTED***'),  # MD5-like hashes
    (r'[a-f0-9]{40}', '***HASH_REDACTED***'),  # SHA1-like hashes
    (r'[a-f0-9]{64}', '***HASH_REDACTED***'),  # SHA256-like hashes
]


def redact_sensitive_data(message: str) -> str:
    """Redact sensitive data from log messages."""
    if not message:
        return message
    
    redacted = message
    for pattern, replacement in SENSITIVE_PATTERNS:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    return redacted


class SensitiveDataFilter(logging.Filter):
    """Filter to redact sensitive data from log records."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Interpolate %-style args FIRST (so %d/%.2f keep working), then
        # redact the fully formatted message. Converting args to strings
        # before interpolation breaks numeric format specifiers.
        if record.args:
            try:
                record.msg = record.getMessage()
                record.args = None
            except Exception:
                pass  # Leave the record untouched; getMessage errors surface later.
        if record.msg:
            try:
                record.msg = redact_sensitive_data(str(record.msg))
            except Exception:
                pass
        return True


def _ensure_log_dirs() -> None:
    """Ensure the log and crash directories exist."""
    os.makedirs(LOG_DIR, exist_ok=True)
    os.makedirs(CRASH_DIR, exist_ok=True)


def _rotating_handler(filename: str) -> RotatingFileHandler:
    """Create a rotating file handler for a component log."""
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, filename),
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    handler.setFormatter(logging.Formatter(log_format, date_format))
    return handler


def setup_component_loggers(
    level: LogLevel = "INFO",
    components: Optional[Dict[str, str]] = None,
) -> Dict[str, logging.Logger]:
    """Configure per-component rotating file loggers.

    Returns a dict of ``{component: logger}`` for the requested components.
    Additive — does not replace the root ``setup_logging``.
    """
    _ensure_log_dirs()
    level_int = getattr(logging, level.upper(), logging.INFO)
    components = components or COMPONENT_LOGS
    loggers: Dict[str, logging.Logger] = {}

    for component, filename in components.items():
        logger = logging.getLogger(f"dash.{component}")
        logger.setLevel(level_int)
        logger.propagate = True
        # Avoid duplicate handlers on repeated calls.
        has_handler = any(
            isinstance(h, RotatingFileHandler) and h.baseFilename.endswith(filename)
            for h in logger.handlers
        )
        if not has_handler:
            logger.addHandler(_rotating_handler(filename))
        logger.addFilter(SensitiveDataFilter())
        loggers[component] = logger

    return loggers


def write_crash_report(
    context: str,
    error: Optional[Exception] = None,
    extra: Optional[Dict] = None,
) -> str:
    """Write a crash report to ``logs/crash/`` and return the file path."""
    _ensure_log_dirs()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"crash_{timestamp}.log"
    path = os.path.join(CRASH_DIR, filename)

    lines = [
        f"=== DASH Crash Report ({timestamp} UTC) ===",
        f"Context: {context}",
    ]
    if error is not None:
        import traceback

        lines.append("Exception:")
        lines.append(f"  {error.__class__.__name__}: {error}")
        lines.append("Traceback:")
        lines.extend(traceback.format_exception(type(error), error, error.__traceback__))
    if extra:
        lines.append("Extra context:")
        for key, value in extra.items():
            lines.append(f"  {key}: {value}")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return path


def setup_logging(level: LogLevel = "INFO") -> None:
    """Configure root logger with a consistent format across environments."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt=date_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Attach the sensitive-data filter to every HANDLER (not the logger):
    # filters on a logger do not run for records propagated from child
    # loggers (e.g. uvicorn.access), but handler filters always run.
    def _protect_handlers(logger_: logging.Logger) -> None:
        logger_.addFilter(SensitiveDataFilter())
        for h in logger_.handlers:
            h.addFilter(SensitiveDataFilter())

    root_logger = logging.getLogger()
    _protect_handlers(root_logger)

    # Reduce noise from third-party libraries in development
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.setLevel(logging.WARNING)
    _protect_handlers(uvicorn_access)  # covers pre-existing uvicorn handlers
    uvicorn_error = logging.getLogger("uvicorn.error")
    uvicorn_error.propagate = True
    _protect_handlers(uvicorn_error)

    # Add rotating file handlers for all components (best-effort).
    try:
        setup_component_loggers(level)
    except Exception:
        # Non-fatal — logging should never crash the app.
        pass


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
