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
def get_sandbox_root() -> Path:
    """Return the configured sandbox root directory."""
    return Path(os.getenv("DASH_FILES_SANDBOX", Path.cwd() / "user_files")).resolve()


def resolve_path_within_sandbox(path_str: str, working_directory: str | None = None) -> Tuple[Path, Path]:
    """Resolve a user-supplied path relative to working_directory and ensure
    the final path is within the sandbox root. Returns (sandbox_root, resolved_path).

    Raises ValueError on path-traversal or invalid paths.
    """
    sandbox = get_sandbox_root()

    # Determine base directory
    if working_directory:
        base = (sandbox / working_directory).resolve()
        if not base.is_relative_to(sandbox):
            base = sandbox
    else:
        base = sandbox

    # Resolve candidate path
    candidate = (base / path_str).resolve()

    # Prevent path traversal: candidate must be inside sandbox
    if not candidate.is_relative_to(sandbox):
        raise ValueError(f"Path traversal detected: '{path_str}' is outside the sandbox")

    return sandbox, candidate


def read_file(path_str: str, working_directory: str | None = None, start_line: int | None = None, end_line: int | None = None) -> dict:
    """Read the contents of a file within the sandbox.

    Args:
        path_str: Path to the file (relative to working_directory or sandbox).
        working_directory: Optional working directory within sandbox.
        start_line: Optional 1-indexed start line.
        end_line: Optional 1-indexed end line (inclusive).

    Returns:
        Dict with path, content, size_bytes, total_lines.

    Raises:
        FileNotFoundError: If the file does not exist.
        IsADirectoryError: If the path is a directory.
    """
    sandbox, file_path = resolve_path_within_sandbox(path_str, working_directory)
    if not file_path.exists():
        raise FileNotFoundError(str(file_path))
    if file_path.is_dir():
        raise IsADirectoryError(str(file_path))

    raw = file_path.read_bytes()
    content = raw.decode("utf-8")
    total_lines = len(content.splitlines())

    if start_line is not None or end_line is not None:
        s = max(0, (start_line or 1) - 1)
        e = min(total_lines, end_line or total_lines)
        lines = content.splitlines()[s:e]
        content = "\n".join(lines)

    logger.info("read_file: %s (size=%d, lines=%d)", str(file_path), len(raw), total_lines)
    return {
        "path": str(file_path.relative_to(sandbox)),
        "content": content,
        "size_bytes": len(raw),
        "total_lines": total_lines,
    }


def write_file(path_str: str, content: str, working_directory: str | None = None, overwrite: bool = True) -> dict:
    sandbox, file_path = resolve_path_within_sandbox(path_str, working_directory)
    if file_path.exists() and not overwrite:
        raise FileExistsError(str(file_path))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = content.encode("utf-8")
    file_path.write_bytes(data)
    logger.info("write_file: %s (size=%d)", str(file_path), len(data))
    return {"path": str(file_path.relative_to(sandbox)), "size_bytes": len(data)}


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