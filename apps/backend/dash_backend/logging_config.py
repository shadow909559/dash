"""Structured logging configuration for the DASH backend."""

import logging
import re
import sys
from typing import Literal

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

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
        if record.msg:
            record.msg = redact_sensitive_data(str(record.msg))
        if record.args:
            record.args = tuple(redact_sensitive_data(str(arg)) for arg in record.args)
        return True


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

    # Add sensitive data filter to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(SensitiveDataFilter())

    # Reduce noise from third-party libraries in development
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").propagate = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger instance."""
    return logging.getLogger(name)
