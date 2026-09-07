"""Project Awareness Engine — automatically understands repositories.

When working inside a repository, DASH automatically infers:
- Folder structure
- Framework
- Dependencies
- Architecture
- Languages
- Running services
- Build tools
- Database
- API
- Recent changes

The engine scans project metadata (package.json, pyproject.toml, etc.) and
builds a project profile so DASH never asks questions it can infer.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_PROJECT = "project"
SOURCE_NEURAL_PROJECT = "neural_project"

# Files that reveal project structure.
_MANIFEST_FILES = [
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "composer.json",
    "Gemfile",
    "mix.exs",
]

# Language detection by extension.
_LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin",
    ".c": "C",
    ".cpp": "C++",
    ".h": "C/C++",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sql": "SQL",
    ".sh": "Shell",
    ".json": "JSON",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".md": "Markdown",
}


@dataclass
class ProjectProfile:
    """An automatically inferred project profile."""

    root: str = ""
    name: str = ""
    framework: str = ""
    languages: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    build_tools: List[str] = field(default_factory=list)
    database: str = ""
    api_framework: str = ""
    has_tests: bool = False
    has_docker: bool = False
    has_ci: bool = False
    recent_changes: List[str] = field(default_factory=list)
    scanned_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root": self.root,
            "name": self.name,
            "framework": self.framework,
            "languages": self.languages,
            "dependencies": self.dependencies,
            "build_tools": self.build_tools,
            "database": self.database,
            "api_framework": self.api_framework,
            "has_tests": self.has_tests,
            "has_docker": self.has_docker,
            "has_ci": self.has_ci,
            "recent_changes": self.recent_changes,
            "scanned_at": self.scanned_at,
        }


class ProjectAwarenessEngine:
    """Scans repositories and builds automatic project profiles."""

    def __init__(self) -> None:
        self._profiles: Dict[str, ProjectProfile] = {}

    # ── Scanning ───────────────────────────────────────────────────────

    def scan(self, root: str) -> ProjectProfile:
        """Scan a project directory and build a profile.

        Best-effort: never raises. Returns an empty profile if the directory
        cannot be scanned.
        """
        root = os.path.abspath(root)
        profile = ProjectProfile(root=root, name=os.path.basename(root))

        try:
            if not os.path.isdir(root):
                return profile

            # Detect languages from file extensions.
            languages: set[str] = set()
            for dirpath, dirnames, filenames in os.walk(root):
                # Skip common noise directories.
                dirnames[:] = [
                    d for d in dirnames
                    if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".cache"}
                ]
                for fname in filenames:
                    ext = os.path.splitext(fname)[1].lower()
                    lang = _LANGUAGE_EXTENSIONS.get(ext)
                    if lang:
                        languages.add(lang)
                # Limit scan depth.
                if dirpath.count(os.sep) - root.count(os.sep) >= 4:
                    dirnames[:] = []
            profile.languages = sorted(languages)

            # Detect manifest files.
            for manifest in _MANIFEST_FILES:
                path = os.path.join(root, manifest)
                if os.path.isfile(path):
                    self._parse_manifest(profile, manifest, path)

            # Detect structure markers.
            profile.has_tests = any(
                os.path.isdir(os.path.join(root, d))
                for d in ("tests", "test", "__tests__", "spec")
            )
            profile.has_docker = any(
                os.path.isfile(os.path.join(root, f))
                for f in ("Dockerfile", "docker-compose.yml", "docker-compose.yaml")
            )
            profile.has_ci = any(
                [
                    os.path.isdir(os.path.join(root, ".github", "workflows")),
                    os.path.isfile(os.path.join(root, ".gitlab-ci.yml")),
                ]
            )

            # Detect database from dependencies.
            self._detect_database(profile)

            # Detect API framework.
            self._detect_api_framework(profile)

            # Recent changes (git log best-effort).
            profile.recent_changes = self._recent_changes(root)

            profile.scanned_at = time.time()
            self._profiles[root] = profile
        except Exception:
            logger.exception("ProjectAwarenessEngine.scan failed for %s", root)

        return profile

    def get_profile(self, root: str) -> Optional[ProjectProfile]:
        """Return a cached profile for a project root."""
        return self._profiles.get(os.path.abspath(root))

    def get_or_scan(self, root: str) -> ProjectProfile:
        """Return a cached profile or scan the directory."""
        cached = self.get_profile(root)
        if cached is not None:
            return cached
        return self.scan(root)

    # ── Helpers ────────────────────────────────────────────────────────

    def _parse_manifest(self, profile: ProjectProfile, manifest: str, path: str) -> None:
        try:
            if manifest == "package.json":
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profile.name = data.get("name", profile.name)
                profile.framework = self._detect_js_framework(data)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                profile.dependencies = sorted(deps.keys())[:30]
                if "typescript" in deps or "ts-node" in deps:
                    if "TypeScript" not in profile.languages:
                        profile.languages.append("TypeScript")
                if "jest" in deps or "vitest" in deps or "mocha" in deps:
                    profile.has_tests = True
                if "next" in deps:
                    profile.framework = "Next.js"
                elif "react" in deps:
                    profile.framework = "React"
                elif "vue" in deps:
                    profile.framework = "Vue"
                elif "express" in deps:
                    profile.framework = "Express"
                elif "fastify" in deps:
                    profile.framework = "Fastify"
                if "prisma" in deps:
                    profile.database = "Prisma"
                elif "sequelize" in deps:
                    profile.database = "Sequelize"
                if "vite" in deps:
                    profile.build_tools.append("Vite")
                if "webpack" in deps:
                    profile.build_tools.append("Webpack")
                if "esbuild" in deps:
                    profile.build_tools.append("esbuild")

            elif manifest == "pyproject.toml":
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                profile.framework = self._detect_python_framework(content)
                if "fastapi" in content:
                    profile.api_framework = "FastAPI"
                    profile.framework = profile.framework or "FastAPI"
                elif "django" in content:
                    profile.framework = "Django"
                elif "flask" in content:
                    profile.framework = "Flask"
                if "pytest" in content:
                    profile.has_tests = True
                if "sqlalchemy" in content:
                    profile.database = "SQLAlchemy"
                elif "tortoise" in content:
                    profile.database = "Tortoise ORM"
                if "poetry" in content:
                    profile.build_tools.append("Poetry")
                elif "uv" in content:
                    profile.build_tools.append("uv")

            elif manifest == "requirements.txt":
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().lower()
                profile.framework = self._detect_python_framework(content)
                if "fastapi" in content:
                    profile.api_framework = "FastAPI"
                elif "django" in content:
                    profile.framework = "Django"
                elif "flask" in content:
                    profile.framework = "Flask"
                if "pytest" in content:
                    profile.has_tests = True
                if "sqlalchemy" in content:
                    profile.database = "SQLAlchemy"

            elif manifest == "Cargo.toml":
                profile.framework = "Cargo"
                profile.build_tools.append("Cargo")
                if "axum" in open(path, "r", encoding="utf-8").read().lower():
                    profile.api_framework = "Axum"

            elif manifest == "go.mod":
                profile.framework = "Go Modules"
                profile.build_tools.append("Go")
                content = open(path, "r", encoding="utf-8").read().lower()
                if "gin" in content:
                    profile.api_framework = "Gin"
                elif "echo" in content:
                    profile.api_framework = "Echo"
                elif "fiber" in content:
                    profile.api_framework = "Fiber"
        except Exception:
            logger.debug("Failed to parse manifest %s", manifest)

    @staticmethod
    def _detect_js_framework(data: Dict[str, Any]) -> str:
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "next" in deps:
            return "Next.js"
        if "react" in deps:
            return "React"
        if "vue" in deps:
            return "Vue"
        if "svelte" in deps:
            return "Svelte"
        if "angular" in deps:
            return "Angular"
        if "express" in deps:
            return "Express"
        if "fastify" in deps:
            return "Fastify"
        return ""

    @staticmethod
    def _detect_python_framework(content: str) -> str:
        lower = content.lower()
        if "fastapi" in lower:
            return "FastAPI"
        if "django" in lower:
            return "Django"
        if "flask" in lower:
            return "Flask"
        if "tornado" in lower:
            return "Tornado"
        return ""

    def _detect_database(self, profile: ProjectProfile) -> None:
        deps_lower = " ".join(profile.dependencies).lower()
        if "postgres" in deps_lower or "psycopg" in deps_lower:
            profile.database = "PostgreSQL"
        elif "mysql" in deps_lower:
            profile.database = "MySQL"
        elif "sqlite" in deps_lower:
            profile.database = "SQLite"
        elif "mongodb" in deps_lower or "pymongo" in deps_lower:
            profile.database = "MongoDB"
        elif "redis" in deps_lower:
            profile.database = "Redis"

    def _detect_api_framework(self, profile: ProjectProfile) -> None:
        if profile.api_framework:
            return
        deps_lower = " ".join(profile.dependencies).lower()
        if "fastapi" in deps_lower:
            profile.api_framework = "FastAPI"
        elif "flask" in deps_lower:
            profile.api_framework = "Flask"
        elif "django" in deps_lower:
            profile.api_framework = "Django REST"
        elif "express" in deps_lower:
            profile.api_framework = "Express"
        elif "graphql" in deps_lower:
            profile.api_framework = "GraphQL"

    @staticmethod
    def _recent_changes(root: str) -> List[str]:
        """Get recent git changes (best-effort)."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "-C", root, "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            if result.returncode == 0:
                return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        except Exception:
            pass
        return []

    # ── Persistence ────────────────────────────────────────────────────

    async def persist_profile(self, session: Any, user_id: str, root: str) -> None:
        """Persist a project profile as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            profile = self.get_or_scan(root)
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps(profile.to_dict(), default=str),
                source=SOURCE_NEURAL_PROJECT,
                category=CATEGORY_PROJECT,
                importance=0.7,
                memory_type="Project",
                title=f"Project: {profile.name}",
            )
        except Exception:
            logger.exception("Failed to persist project profile")


# Global singleton
_project_awareness_engine: Optional[ProjectAwarenessEngine] = None


def get_project_awareness_engine() -> ProjectAwarenessEngine:
    """Return the global ProjectAwarenessEngine singleton."""
    global _project_awareness_engine
    if _project_awareness_engine is None:
        _project_awareness_engine = ProjectAwarenessEngine()
    return _project_awareness_engine