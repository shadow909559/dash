"""Goal Understanding Engine.

Infers the user's underlying goal and sub-goals from a request. This is deeper
than keyword matching — it decomposes a request into a possible goal, a set of
sub-goals, and the tools/domains DASH can use to satisfy it.

The result feeds the pipeline so DASH can plan multi-step actions instead of just
answering a single command.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class GoalUnderstanding:
    """The inferred goal and decomposition of a user request."""

    raw_request: str
    goal: str = ""
    category: str = "general"
    sub_goals: List[str] = field(default_factory=list)
    domains: List[str] = field(default_factory=list)
    suggested_tools: List[str] = field(default_factory=list)
    priority: str = "normal"  # "urgent" | "important" | "normal" | "background"
    confidence: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "category": self.category,
            "sub_goals": self.sub_goals,
            "domains": self.domains,
            "suggested_tools": self.suggested_tools,
            "priority": self.priority,
            "confidence": round(self.confidence, 3),
        }


# Domain keyword groups -> (domain, category, suggested tools)
_DOMAINS: List[tuple[str, str, List[str], List[str]]] = [
    ("calendar", "schedule", ["calendar", "schedule", "appointment", "meeting", "remind", "event"], ["calendar", "reminders"]),
    ("coding", "coding", ["code", "bug", "fix", "refactor", "function", "script", "repo", "python", "javascript", "typescript", "compile"], ["code_runner", "terminal", "editor"]),
    ("research", "research", ["research", "search", "find", "look up", "investigate", "article", "source", "document", "report"], ["web_search", "browser", "rag"]),
    ("email", "communication", ["email", "send mail", "inbox", "draft", "reply", "message"], ["email", "compose"]),
    ("automation", "automation", ["automate", "script", "when i", "every day", "schedule", "daily", "weekly", "if this"], ["automation", "scheduler"]),
    ("desktop", "system", ["open", "launch", "window", "desktop", "folder", "file", "app", "application", "close"], ["desktop_automation", "filesystem"]),
    ("browser", "research", ["browse", "website", "url", "web page", "chrome", "edge", "navigate"], ["browser"]),
    ("audio", "media", ["play", "music", "song", "volume", "stop", "pause", "audio", "video"], ["media", "audio"]),
    ("home", "automation", ["lights", "thermostat", "temperature", "turn on", "turn off", "smart"], ["smarthome"]),
    ("phone", "communication", ["call", "text", "sms", "phone", "mobile", "android"], ["phone", "android"]),
]


class GoalUnderstandingEngine:
    """Decomposes a raw user request into a structured goal."""

    def understand(self, request: str) -> GoalUnderstanding:
        req = (request or "").strip()
        lower = req.lower()

        domain = "general"
        category = "general"
        tools: List[str] = []
        for d, cat, keywords, suggested in _DOMAINS:
            if any(k in lower for k in keywords):
                domain = d
                category = cat
                tools = suggested
                break

        # Infer the top-level goal: the verb/intent phrase.
        goal = self._infer_goal(req, lower)

        # Decompose into sub-goals based on domain.
        sub_goals = self._decompose(lower, domain)

        # Priority heuristic.
        priority = self._infer_priority(lower)

        confidence = min(0.95, 0.5 + 0.1 * len(sub_goals) + (0.1 if domain != "general" else 0))

        return GoalUnderstanding(
            raw_request=req,
            goal=goal,
            category=category,
            sub_goals=sub_goals,
            domains=[domain],
            suggested_tools=tools,
            priority=priority,
            confidence=confidence,
        )

    def _infer_goal(self, raw: str, lower: str) -> str:
        """Extract a concise goal phrase from the request."""
        # Strip leading conversational filler.
        for prefix in ("please ", "can you ", "could you ", "would you ", "i need you to ", "hey dash ", "dash "):
            if lower.startswith(prefix):
                raw = raw[len(prefix):]
                break

        # If there's a verb phrase, cap at ~12 words.
        words = raw.split()
        if len(words) > 12:
            return " ".join(words[:12]) + "…"
        return raw or "General request"

    def _decompose(self, lower: str, domain: str) -> List[str]:
        """Produce a list of sub-goals for the domain."""
        if domain == "coding":
            subs = ["Understand the codebase/context", "Identify the relevant module", "Implement or fix the change", "Verify the result"]
            if "test" in lower:
                subs.append("Run tests")
            if "deploy" in lower or "release" in lower:
                subs.append("Prepare deployment")
            return subs
        if domain == "research":
            subs = ["Clarify the research question", "Search relevant sources", "Synthesize findings", "Summarize for the user"]
            if "pdf" in lower or "document" in lower:
                subs.append("Extract document content")
            return subs
        if domain == "calendar":
            subs = ["Check the calendar", "Identify available time", "Schedule the event", "Set a reminder"]
            return subs
        if domain == "email":
            subs = ["Read relevant messages", "Draft the reply/email", "Confirm recipient", "Send or save draft"]
            return subs
        if domain == "automation":
            subs = ["Understand the trigger", "Define the action", "Set up the schedule", "Test the automation"]
            return subs
        if domain == "desktop":
            subs = ["Locate the target", "Perform the action", "Confirm the result"]
            return subs
        if domain == "browser":
            subs = ["Open the browser", "Navigate to the target", "Extract information"]
            return subs
        if domain == "audio":
            subs = ["Find the media", "Play/pause/control", "Verify playback"]
            return subs
        if domain == "home":
            subs = ["Identify the device", "Issue the control command", "Confirm state"]
            return subs
        if domain == "phone":
            subs = ["Identify the contact/device", "Route via companion", "Send/perform action", "Confirm delivery"]
            return subs
        return ["Understand the request", "Perform the action", "Confirm the result"]

    def _infer_priority(self, lower: str) -> str:
        """Classify the priority of the request."""
        urgent = ["asap", "urgent", "immediately", "right now", "emergency", "critical", "now", "important", "deadline"]
        if any(k in lower for k in urgent):
            return "urgent"
        background = ["background", "later", "when i have time", "eventually", "someday", "remind me to"]
        if any(k in lower for k in background):
            return "background"
        return "normal"


# Global singleton
_goal_engine: Optional[GoalUnderstandingEngine] = None


def get_goal_understanding_engine() -> GoalUnderstandingEngine:
    """Return the global GoalUnderstandingEngine singleton."""
    global _goal_engine
    if _goal_engine is None:
        _goal_engine = GoalUnderstandingEngine()
    return _goal_engine
