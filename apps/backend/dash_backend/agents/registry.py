"""Agent registry: built-in agent definitions."""

from __future__ import annotations

from typing import Dict

# Built-in agent definitions. These are lightweight and can be
# extended at runtime via the /agents API.
BUILTIN_AGENTS: Dict[str, dict] = {
    "general": {
        "name": "General Assistant",
        "description": "Helpful general-purpose assistant.",
        "system_prompt": "You are a helpful assistant.",
        "allowed_tools": None,
    },
    "coding": {
        "name": "Coding Assistant",
        "description": "Focused on code, debugging and development tasks.",
        "system_prompt": "You are a coding assistant. Provide code snippets and explanations.",
        "allowed_tools": ["read_file", "search_files", "write_file"],
    },
    "research": {
        "name": "Research Assistant",
        "description": "Helps with research, summarization and citations.",
        "system_prompt": "You are a research assistant. Provide concise summaries and cite sources.",
        "allowed_tools": ["search_files"],
    },
    "file": {
        "name": "File Assistant",
        "description": "Performs file-centric tasks safely.",
        "system_prompt": "You are a file assistant. Use file tools carefully and respect sandboxing.",
        "allowed_tools": ["read_file", "write_file", "list_directory", "search_files"],
    },
}
