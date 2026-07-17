"""Filesystem service helpers: sandboxing, path validation, and logging for filesystem tools.

This centralizes path resolution and security checks so existing filesystem tools
can reuse consistent behavior.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Sandbox root can be overridden by the DASH_FILES_SANDBOX environment variable.
# Default: repository working directory / user_files
DEFAULT_SANDBOX = Path(os.getenv("DASH_FILES_SANDBOX", Path.cwd() / "user_files")).resolve()
DEFAULT_SANDBOX.mkdir(parents=True, exist_ok=True)


def get_sandbox_root() -> Path:
    """Return the configured sandbox root directory."""
    return DEFAULT_SANDBOX


def resolve_path_within_sandbox(path_str: str, working_directory: str | None = None) -> Tuple[Path, Path]:
    """Resolve a user-supplied path relative to working_directory and ensure
    the final path is within the sandbox root. Returns (sandbox_root, resolved_path).

    Raises ValueError on path-traversal or invalid paths.
    """
    sandbox = get_sandbox_root()

    # Base directory for resolution is either the provided working_directory (relative to sandbox)
    # or the sandbox itself.
    if working_directory:
        base = (sandbox / working_directory).resolve()
    else:
        base = sandbox

    # Ensure base is inside sandbox
    try:
        base.relative_to(sandbox)
    except Exception:
        # If base is outside sandbox, reset to sandbox
        base = sandbox

    candidate = (base / path_str).resolve()

    # Prevent path traversal: candidate must be inside sandbox
    try:
        candidate.relative_to(sandbox)
    except Exception:
        raise ValueError(f"Path traversal detected: '{path_str}' is outside the sandbox")

    return sandbox, candidate


def read_file(path_str: str, working_directory: str | None = None, max_size: int = 100 * 1024) -> dict:
    sandbox, file_path = resolve_path_within_sandbox(path_str, working_directory)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    if not file_path.is_file():
        raise IsADirectoryError(str(file_path))
    if file_path.stat().st_size > max_size:
        raise OSError(f"File too large: {file_path.stat().st_size} bytes")
    content = file_path.read_text(encoding="utf-8", errors="replace")
    logger.info("read_file: %s (size=%d)", str(file_path), file_path.stat().st_size)
    return {
        "path": str(file_path.relative_to(sandbox)),
        "size_bytes": file_path.stat().st_size,
        "content": content,
    }


def write_file(path_str: str, content: str, working_directory: str | None = None, overwrite: bool = True) -> dict:
    sandbox, file_path = resolve_path_within_sandbox(path_str, working_directory)
    if file_path.exists() and not overwrite:
        raise FileExistsError(str(file_path))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")
    logger.info("write_file: %s (size=%d)", str(file_path), file_path.stat().st_size)
    return {"path": str(file_path.relative_to(sandbox)), "size_bytes": file_path.stat().st_size}


def list_directory(path_str: str | None = None, working_directory: str | None = None, recursive: bool = False, pattern: str | None = None) -> dict:
    sandbox, base_path = resolve_path_within_sandbox(path_str or ".", working_directory)
    if not base_path.exists():
        raise FileNotFoundError(str(base_path))
    if not base_path.is_dir():
        raise NotADirectoryError(str(base_path))

    entries = []
    if recursive:
        iterator = base_path.rglob("*")
    else:
        iterator = base_path.iterdir()

    for item in iterator:
        try:
            rel = item.relative_to(sandbox)
        except Exception:
            continue
        if pattern and not item.match(pattern):
            continue
        entries.append({
            "name": item.name,
            "path": str(rel),
            "type": "directory" if item.is_dir() else "file",
            "size_bytes": item.stat().st_size if item.is_file() else 0,
        })

    entries.sort(key=lambda e: (0 if e["type"] == "directory" else 1, e["name"]))
    logger.info("list_directory: %s returned %d entries", str(base_path), len(entries))
    return {"path": str(base_path.relative_to(sandbox)), "entries": entries, "total_entries": len(entries)}


def search_files(pattern: str, path_str: str | None = None, working_directory: str | None = None, file_pattern: str | None = None, max_results: int = 50) -> dict:
    sandbox, base_path = resolve_path_within_sandbox(path_str or ".", working_directory)
    if not base_path.exists() or not base_path.is_dir():
        raise FileNotFoundError(str(base_path))

    import re

    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"Invalid regex: {exc}")

    results = []
    max_size = 1024 * 1024

    for item in base_path.rglob("*"):
        if not item.is_file():
            continue
        if file_pattern and not item.match(file_pattern):
            continue
        if item.stat().st_size > max_size:
            continue
        try:
            rel = item.relative_to(sandbox)
            content = item.read_text(encoding="utf-8", errors="replace")
            for match in regex.finditer(content):
                if len(results) >= max_results:
                    break
                line_num = content[: match.start()].count("\n") + 1
                start = max(0, match.start() - 40)
                end = min(len(content), match.end() + 40)
                context_str = content[start:end].replace("\n", " ").strip()
                results.append({
                    "file": str(rel),
                    "line": line_num,
                    "match": match.group(),
                    "context": context_str,
                })
        except (OSError, UnicodeDecodeError):
            continue
        if len(results) >= max_results:
            break

    logger.info("search_files: pattern=%s path=%s matches=%d", pattern, str(base_path), len(results))
    return {"pattern": pattern, "search_path": str(base_path.relative_to(sandbox)), "results": results, "total_matches": len(results)}
