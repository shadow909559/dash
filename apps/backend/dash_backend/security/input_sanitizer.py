"""Input sanitization service for DASH.

Prevents path traversal, command injection, and other input-based attacks.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any


# Regex patterns for detecting malicious input
MALICIOUS_PATTERNS = [
    re.compile(r"\.\./|\.\.\\"),          # Path traversal
    re.compile(r"[|;&`$><]"),             # Shell metacharacters
    re.compile(r"__import__|exec\s*\("),  # Python code injection
    re.compile(r"\beval\s*\("),           # eval injection
    re.compile(r"\brm\s+-rf\b"),          # Dangerous commands
    re.compile(r"\bformat\s+[c-z]:\s*/q"),  # Disk format commands
]


class InputValidationError(ValueError):
    """Raised when input validation fails."""


def sanitize_path(path: str, base_dir: str | None = None) -> str:
    """Sanitize a file path to prevent path traversal attacks.

    Args:
        path: The input path to sanitize.
        base_dir: Optional base directory to restrict paths to.

    Returns:
        The resolved absolute path.

    Raises:
        InputValidationError: If the path is invalid or attempts traversal.
    """
    if not path or not isinstance(path, str):
        raise InputValidationError("Path must be a non-empty string")

    # Strip null bytes
    path = path.replace("\x00", "")

    # Remove any prefix like file://
    if path.startswith("file://"):
        path = path[7:]

    # Resolve the path
    try:
        p = Path(path).resolve()
    except (OSError, RuntimeError) as exc:
        raise InputValidationError(f"Invalid path: {exc}") from exc

    # Check for path traversal
    if base_dir:
        base = Path(base_dir).resolve()
        try:
            p.relative_to(base)
        except ValueError as exc:
            raise InputValidationError(
                f"Path traversal detected: {path} is outside {base_dir}"
            ) from exc

    # Check for malicious patterns
    for pattern in MALICIOUS_PATTERNS:
        if pattern.search(str(p)):
            raise InputValidationError(f"Path contains prohibited pattern: {p}")

    return str(p)

def sanitize_for_llm(text: str, max_length: int = 10000) -> str | None:
    """
    Sanitize user input before sending it to an LLM.

    Optional max_length can be provided to override the default.
    Returns None when the input is None.
    """
    if text is None:
        return None
    return sanitize_text(text, max_length=max_length)


def sanitize_memory_context(text: str) -> str:
    """
    Sanitize memory context before injecting into prompts.

    Memory contexts are larger but should still be bounded to avoid huge prompts.
    """
    return sanitize_text(text, max_length=5000)


def sanitize_user_input(text: str, max_length: int = 10000) -> str | None:
    """
    Sanitize general user input.

    Allows an optional max_length override used by callers/tests when needed.
    Returns None when the input is None.
    """
    if text is None:
        return None
    return sanitize_text(text, max_length=max_length)


def sanitize_goal_input(name: str, description: str | None = None) -> tuple[str, str | None]:
    """
    Sanitize planner/goal input.

    Returns a tuple (sanitized_name, sanitized_description_or_None).
    """
    # Max lengths chosen to keep prompts concise
    MAX_GOAL_NAME_LENGTH = 200
    MAX_GOAL_DESCRIPTION_LENGTH = 2000

    if not isinstance(name, str):
        raise InputValidationError("Goal name must be a string")
    sanitized_name = sanitize_text(name, max_length=MAX_GOAL_NAME_LENGTH)

    if not description:
        return sanitized_name, None
    if not isinstance(description, str):
        raise InputValidationError("Goal description must be a string")
    sanitized_description = sanitize_text(description, max_length=MAX_GOAL_DESCRIPTION_LENGTH)
    return sanitized_name, sanitized_description
def sanitize_filename(filename: str) -> str:
    """Sanitize a filename by removing dangerous characters.

    Args:
        filename: The input filename.

    Returns:
        A sanitized filename string.
    """
    if not filename or not isinstance(filename, str):
        raise InputValidationError("Filename must be a non-empty string")

    # Remove path separators
    filename = filename.replace("/", "").replace("\\", "")

    # Remove null bytes
    filename = filename.replace("\x00", "")

    # Remove leading dots and spaces
    filename = filename.lstrip(". ")

    # Remove any remaining dangerous characters
    filename = re.sub(r'[<>:"|?*]', "", filename)

    if not filename:
        raise InputValidationError("Filename is empty after sanitization")

    return filename


def sanitize_command(command: str) -> str:
    """Validate and sanitize a shell command.

    Args:
        command: The command string to validate.

    Returns:
        The sanitized command.

    Raises:
        InputValidationError: If the command contains malicious patterns.
    """
    if not command or not isinstance(command, str):
        raise InputValidationError("Command must be a non-empty string")

    # Check for malicious patterns
    for pattern in MALICIOUS_PATTERNS:
        if pattern.search(command):
            raise InputValidationError(f"Command contains prohibited pattern: {pattern.pattern}")

    return command.strip()


def sanitize_search_query(query: str, max_length: int = 500) -> str:
    """Sanitize a search query.

    Args:
        query: The search query string.
        max_length: Maximum allowed length.

    Returns:
        The sanitized query.
    """
    if not isinstance(query, str):
        raise InputValidationError("Query must be a string")

    # Trim whitespace
    query = query.strip()

    # Enforce max length
    if len(query) > max_length:
        query = query[:max_length]

    # Remove control characters (except newline and tab)
    query = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", query)

    return query


def validate_json_payload(payload: Any, max_depth: int = 10) -> dict | list | None:
    """Validate and sanitize a JSON payload against nested structure attacks.

    Args:
        payload: The JSON-deserialized payload.
        max_depth: Maximum allowed nesting depth.

    Returns:
        The validated payload.

    Raises:
        InputValidationError: If payload is too deeply nested or malformed.
    """
    if payload is None:
        return None

    def _check_depth(obj: Any, depth: int = 0) -> None:
        if depth > max_depth:
            raise InputValidationError(
                f"Payload exceeds maximum nesting depth of {max_depth}"
            )
        if isinstance(obj, dict):
            for key, value in obj.items():
                if not isinstance(key, str):
                    raise InputValidationError(
                        f"Dictionary key must be string, got {type(key).__name__}"
                    )
                _check_depth(value, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _check_depth(item, depth + 1)

    _check_depth(payload)
    return payload


def sanitize_text(text: str, max_length: int = 10000) -> str:
    """Sanitize text content.

    Args:
        text: The text to sanitize.
        max_length: Maximum allowed length.

    Returns:
        The sanitized text (truncated if needed).
    """
    if not isinstance(text, str):
        raise InputValidationError("Text must be a string")

    # Enforce max length
    if len(text) > max_length:
        text = text[:max_length]

    # Remove control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text


REDIRECT_URL_PATTERN = re.compile(
    r"^(https?://|/|#)[\w\-./?=&%+#@~!$'()*+,;:]+$"
)


def validate_redirect_url(url: str) -> str:
    """Validate a redirect URL to prevent open redirect attacks.

    Args:
        url: The redirect URL to validate.

    Returns:
        The validated URL.

    Raises:
        InputValidationError: If the URL is unsafe.
    """
    if not url or not isinstance(url, str):
        raise InputValidationError("URL must be a non-empty string")

    # Allow relative paths, same-origin, or known safe protocols
    if url.startswith("http://") or url.startswith("https://"):
        # For absolute URLs, only allow localhost in development
        from dash_backend.config import get_settings

        settings = get_settings()
        if settings.is_development:
            return url

        # In production, restrict to same origin
        raise InputValidationError("External redirect URLs are not allowed in production")

    # Allow relative paths and anchors
    if url.startswith("/") or url.startswith("#"):
        if REDIRECT_URL_PATTERN.match(url):
            return url

    raise InputValidationError(f"Unsafe redirect URL: {url}")

def detect_prompt_injection(text: str) -> bool:
    """
    Basic prompt injection detection.
    Returns True if suspicious prompt injection patterns are found.
    """

    if not isinstance(text, str):
        return False

    patterns = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"ignore\s+the\s+above",
        r"disregard\s+(all\s+)?previous\s+instructions",
        r"disregard\s+the\s+above",
        r"forget\s+(all\s+|everything\s+)?(the\s+)?above",
        r"override\s+(all\s+)?previous\s+instructions",
        r"system\s*:",
        r"\[/?system\]",
        r"\[/?instruction\]",
        r"\[/?directive\]",
        r"developer\s*:",
        r"assistant\s*:",
        r"</system>",
        r"<system>",
        r"you\s+are\s+now\s+",
        r"pretend\s+to\s+be\b",
        r"simulate\s+a\s+different\b",
        r"roleplay\s+as\b",
        r"reveal\s+your\s+prompt",
        r"show\s+your\s+system\s+prompt",
        r"bypass\s+safety",
        r"act\s+as",
        r"(?m)^#{1,6}\s+instruction\b",
        r"(?m)^[-=]{3,}\s+instruction\b",
        r"(?m)^<{3,}\s+instruction\b",
    ]

    text = text.lower()

    return any(re.search(p, text, re.IGNORECASE) for p in patterns)