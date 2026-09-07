"""Personality Engine — adapts DASH's communication style to each user.

Learns over time:
- Preferred response length (concise / balanced / detailed)
- Humor preference (none / light / playful)
- Technical depth preference (beginner / intermediate / expert)
- Communication style (formal / casual / professional)
- Working hours and productivity habits
- Favorite tools and frequently used software
- Common tasks

The engine produces a personality profile that the pipeline uses to shape
responses naturally — never repetitive, never always the same way.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.memory import service as memory_service
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_PERSONALITY = "personality"
SOURCE_NEURAL_PERSONALITY = "neural_personality"

# Response length buckets.
LENGTH_CONCISE = "concise"
LENGTH_BALANCED = "balanced"
LENGTH_DETAILED = "detailed"

# Humor buckets.
HUMOR_NONE = "none"
HUMOR_LIGHT = "light"
HUMOR_PLAYFUL = "playful"

# Technical depth buckets.
DEPTH_BEGINNER = "beginner"
DEPTH_INTERMEDIATE = "intermediate"
DEPTH_EXPERT = "expert"

# Communication style buckets.
STYLE_FORMAL = "formal"
STYLE_CASUAL = "casual"
STYLE_PROFESSIONAL = "professional"


@dataclass
class PersonalityProfile:
    """The learned communication personality for a user."""

    response_length: str = LENGTH_BALANCED
    humor: str = HUMOR_LIGHT
    technical_depth: str = DEPTH_INTERMEDIATE
    style: str = STYLE_PROFESSIONAL
    working_hours: List[int] = field(default_factory=list)
    favorite_tools: List[str] = field(default_factory=list)
    common_tasks: List[str] = field(default_factory=list)
    observations: int = 0
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "response_length": self.response_length,
            "humor": self.humor,
            "technical_depth": self.technical_depth,
            "style": self.style,
            "working_hours": self.working_hours,
            "favorite_tools": self.favorite_tools,
            "common_tasks": self.common_tasks,
            "observations": self.observations,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PersonalityProfile":
        return cls(
            response_length=data.get("response_length", LENGTH_BALANCED),
            humor=data.get("humor", HUMOR_LIGHT),
            technical_depth=data.get("technical_depth", DEPTH_INTERMEDIATE),
            style=data.get("style", STYLE_PROFESSIONAL),
            working_hours=data.get("working_hours", []),
            favorite_tools=data.get("favorite_tools", []),
            common_tasks=data.get("common_tasks", []),
            observations=data.get("observations", 0),
            updated_at=data.get("updated_at", time.time()),
        )


class PersonalityEngine:
    """Learns and applies a per-user communication personality."""

    # Signals that indicate a preference for concise answers.
    CONCISE_SIGNALS = [
        "short", "brief", "quick", "tl;dr", "summarize", "in short",
        "one line", "concise", "keep it short", "just the answer",
    ]

    # Signals that indicate a preference for detailed answers.
    DETAILED_SIGNALS = [
        "detailed", "in depth", "explain", "elaborate", "full",
        "comprehensive", "thorough", "step by step", "walk me through",
        "more detail", "deep dive",
    ]

    # Signals that indicate humor is welcome.
    HUMOR_SIGNALS = [
        "funny", "joke", "lol", "haha", "make me laugh", "humor",
        "lighten up", "entertain me",
    ]

    # Signals that indicate formal communication.
    FORMAL_SIGNALS = [
        "formal", "professional tone", "business", "official",
        "proper", "polite",
    ]

    # Signals that indicate casual communication.
    CASUAL_SIGNALS = [
        "casual", "chill", "relaxed", "informal", "buddy", "dude",
        "hey", "yo",
    ]

    # Signals that indicate expert-level technical depth.
    EXPERT_SIGNALS = [
        "expert", "advanced", "senior", "architect", "internals",
        "under the hood", "low level", "performance tuning",
    ]

    # Signals that indicate beginner-level technical depth.
    BEGINNER_SIGNALS = [
        "beginner", "new to", "explain like i'm 5", "eli5", "simple",
        "basic", "starter", "novice",
    ]

    def __init__(self, session: Any) -> None:
        self._session = session

    # ── Learning ───────────────────────────────────────────────────────

    async def observe(
        self,
        user_id: str,
        query: str,
        *,
        response_length: Optional[int] = None,
        feedback: Optional[str] = None,
    ) -> None:
        """Learn from a user interaction.

        ``response_length`` is the number of words in DASH's response.
        ``feedback`` may contain explicit user feedback ("too long", "funny!").
        """
        try:
            profile = await self.get_profile(user_id)
            profile.observations += 1
            profile.updated_at = time.time()

            lower = (query or "").lower()
            feedback_lower = (feedback or "").lower()

            # Response length signals.
            if any(s in lower for s in self.CONCISE_SIGNALS) or "too long" in feedback_lower:
                profile.response_length = LENGTH_CONCISE
            elif any(s in lower for s in self.DETAILED_SIGNALS) or "too short" in feedback_lower:
                profile.response_length = LENGTH_DETAILED
            elif response_length is not None:
                # Heuristic: very short responses suggest concise preference.
                if response_length < 30:
                    profile.response_length = LENGTH_CONCISE
                elif response_length > 300:
                    profile.response_length = LENGTH_DETAILED
                else:
                    profile.response_length = LENGTH_BALANCED

            # Humor signals.
            if any(s in lower for s in self.HUMOR_SIGNALS) or "funny" in feedback_lower:
                profile.humor = HUMOR_PLAYFUL
            elif "not funny" in feedback_lower or "stop joking" in feedback_lower:
                profile.humor = HUMOR_NONE

            # Style signals.
            if any(s in lower for s in self.FORMAL_SIGNALS):
                profile.style = STYLE_FORMAL
            elif any(s in lower for s in self.CASUAL_SIGNALS):
                profile.style = STYLE_CASUAL

            # Technical depth signals.
            if any(s in lower for s in self.EXPERT_SIGNALS):
                profile.technical_depth = DEPTH_EXPERT
            elif any(s in lower for s in self.BEGINNER_SIGNALS):
                profile.technical_depth = DEPTH_BEGINNER

            # Working hours: infer from current hour if the user is active.
            hour = dt.datetime.now().hour
            if hour not in profile.working_hours:
                profile.working_hours.append(hour)
                profile.working_hours.sort()
                profile.working_hours = profile.working_hours[-24:]

            # Common tasks: track repeated query categories.
            task = self._extract_task(query)
            if task and task not in profile.common_tasks:
                profile.common_tasks.append(task)
                profile.common_tasks = profile.common_tasks[-20:]

            await self._save_profile(user_id, profile)
        except Exception:
            logger.exception("PersonalityEngine.observe failed")

    async def observe_tool(self, user_id: str, tool: str) -> None:
        """Record a frequently used tool."""
        try:
            profile = await self.get_profile(user_id)
            tool = str(tool or "").strip()
            if tool and tool not in profile.favorite_tools:
                profile.favorite_tools.append(tool)
                profile.favorite_tools = profile.favorite_tools[-15:]
            await self._save_profile(user_id, profile)
        except Exception:
            logger.exception("PersonalityEngine.observe_tool failed")

    # ── Accessors ──────────────────────────────────────────────────────

    async def get_profile(self, user_id: str) -> PersonalityProfile:
        """Return the learned personality profile for a user."""
        memories, _ = await memory_service.get_user_memories(
            self._session,
            user_id,
            category=CATEGORY_PERSONALITY,
            limit=1,
            sort_by="recency",
        )
        if memories:
            try:
                data = json.loads(memories[0].content)
                return PersonalityProfile.from_dict(data)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Failed to decode personality profile", exc_info=True)
        return PersonalityProfile()

    async def apply_style(self, user_id: str, text: str) -> str:
        """Apply the learned personality style to a response.

        This is intentionally lightweight — it adjusts greeting/formatting
        without rewriting content. The LLM prompt layer uses the profile for
        deeper style shaping.
        """
        profile = await self.get_profile(user_id)
        text = (text or "").strip()
        if not text:
            return text

        # Casual style: relax formal openings.
        if profile.style == STYLE_CASUAL:
            text = text.replace("I would recommend", "I'd suggest")
            text = text.replace("It is important to", "It's worth")
            text = text.replace("I am", "I'm")

        # Concise: trim trailing pleasantries.
        if profile.response_length == LENGTH_CONCISE:
            for phrase in [
                " Let me know if you have any questions.",
                " Feel free to ask if you need more help.",
                " I hope this helps.",
            ]:
                if text.endswith(phrase):
                    text = text[: -len(phrase)]

        return text

    # ── Persistence ────────────────────────────────────────────────────

    async def _save_profile(self, user_id: str, profile: PersonalityProfile) -> None:
        """Persist the personality profile as a memory."""
        try:
            await memory_service.save_memory(
                self._session,
                user_id,
                json.dumps(profile.to_dict(), default=str),
                source=SOURCE_NEURAL_PERSONALITY,
                category=CATEGORY_PERSONALITY,
                importance=0.75,
                memory_type="Preference",
                title="Personality profile",
            )
        except Exception:
            logger.exception("Failed to persist personality profile")

    @staticmethod
    def _extract_task(query: str) -> Optional[str]:
        """Extract a coarse task category from a query."""
        lower = (query or "").lower()
        task_map = {
            "coding": ["code", "bug", "fix", "refactor", "function", "script", "compile"],
            "research": ["research", "search", "find", "look up", "investigate"],
            "email": ["email", "send mail", "inbox", "draft", "reply"],
            "calendar": ["calendar", "schedule", "meeting", "appointment", "remind"],
            "desktop": ["open", "launch", "window", "folder", "file", "app"],
            "browser": ["browse", "website", "url", "chrome", "navigate"],
            "automation": ["automate", "script", "when i", "every day", "schedule"],
        }
        for task, keywords in task_map.items():
            if any(k in lower for k in keywords):
                return task
        return None


# Global singleton (session-backed compatibility accessor).
#
# ``PersonalityEngine`` requires an ``AsyncSession`` for memory persistence,
# so unlike the stateless neural engines it cannot be a plain module-level
# object. This shim lazily binds a session on first call so older code/tests
# that still invoke ``get_personality_engine()`` keep working. New request
# handling code should instantiate ``PersonalityEngine(session)`` with an
# explicit ``AsyncSession`` from the DB dependency for proper lifecycle.
_personality_engine: Optional["PersonalityEngine"] = None


def get_personality_engine() -> "PersonalityEngine":
    """Return a session-backed ``PersonalityEngine`` singleton.

    Compatibility wrapper for older code/tests that still call
    ``get_personality_engine()`` directly. For production request handling,
    prefer ``PersonalityEngine(session)`` with a request-scoped ``AsyncSession``.
    """
    global _personality_engine
    if _personality_engine is None:
        # Lazy import to avoid a module-import cycle with dash_backend.db.session.
        from dash_backend.db.session import AsyncSessionLocal

        _personality_engine = PersonalityEngine(AsyncSessionLocal())
    return _personality_engine

