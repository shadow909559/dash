"""Fast-Path Executor — instant execution for single-tool goals.

When a goal maps directly to a known tool, skip the LLM entirely and
execute the tool immediately. This turns a 50-60s LLM round-trip into
a <1s direct tool call.

The fast-path uses:
1. Keyword patterns matched against goal descriptions
2. Experience cache patterns from past successful goals
3. Confidence scoring to avoid false positives

If the fast-path doesn't match (low confidence), the goal falls through
to the normal LLM-driven observe→think→act loop.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class FastPathMatch:
    """A direct tool mapping for a goal."""
    tool_name: str
    tool_args: dict[str, Any]
    confidence: float  # 0.0 to 1.0
    reasoning: str


# ── Pattern definitions ─────────────────────────────────────────────────

# Each pattern: (compiled_regex, tool_name, args_extractor, confidence)
# args_extractor receives the regex match and returns tool args dict

def _build_patterns() -> list[tuple[re.Pattern, str, callable, float]]:
    """Build the fast-path pattern library."""
    patterns = []

    def add(regex: str, tool: str, extractor: callable, conf: float = 0.9):
        patterns.append((re.compile(regex, re.IGNORECASE), tool, extractor, conf))

    # ── System info ──────────────────────────────────────────────
    add(
        r"^(check|show|get|what('s| is)|tell me)\s+(system\s+)?(health|status|info|stats|info)$",
        "system_info", lambda m: {}, 0.95,
    )
    add(
        r"^(check|show|get)\s+(cpu|processor|ram|memory|disk|drive|battery)",
        "system_info", lambda m: {}, 0.9,
    )

    # ── File operations ──────────────────────────────────────────
    add(
        r"^(find|search|locate|where)\s+(all\s+)?(large|big|biggest)\s+(files?)",
        "find_large_files",
        lambda m: {"path": str(__import__("pathlib").Path.home())},
        0.9,
    )
    add(
        r"^(find|search|locate)\s+(all\s+)?(large|big)\s+files?\s+(in|on)\s+(.+)",
        "find_large_files",
        lambda m: {"path": m.group(5).strip()},
        0.85,
    )

    # ── Downloads organization ───────────────────────────────────
    add(
        r"^(organize|sort|clean up?|tidy)\s+(my\s+)?downloads?$",
        "organize_downloads", lambda m: {"dry_run": False}, 0.9,
    )
    add(
        r"^(organize|sort)\s+(my\s+)?downloads?\s*(dry\s*run|preview|simulate)?",
        "organize_downloads",
        lambda m: {"dry_run": bool(m.group(3))},
        0.9,
    )

    # ── Process management ───────────────────────────────────────
    add(
        r"^(list|show|what('s| is))\s+(running\s+)?(processes?|apps?|programs?)$",
        "list_processes", lambda m: {}, 0.9,
    )

    # ── Clipboard ────────────────────────────────────────────────
    add(
        r"^(copy|clipboard)\s+(.+)",
        "copy_text",
        lambda m: {"text": m.group(2).strip()},
        0.85,
    )
    add(
        r"^(read|get|show)\s+(the\s+)?clipboard$",
        "read_clipboard", lambda m: {}, 0.9,
    )

    # ── System actions ───────────────────────────────────────────
    add(r"^(lock|secure)\s+(my\s+)?(pc|computer|workstation|screen)$",
        "lock_workstation", lambda m: {}, 0.95)
    add(r"^(shutdown|shut down|turn off)\s+(my\s+)?(pc|computer)$",
        "shutdown", lambda m: {}, 0.9)
    add(r"^(restart|reboot)\s+(my\s+)?(pc|computer)$",
        "restart", lambda m: {}, 0.9)
    add(r"^(sleep|suspend)\s+(my\s+)?(pc|computer)$",
        "sleep", lambda m: {}, 0.9)

    # ── Volume ───────────────────────────────────────────────────
    add(r"^(get|what('s| is))\s+(the\s+)?volume$",
        "get_volume", lambda m: {}, 0.9)
    add(r"^(mute|unmute|toggle\s+mute)$",
        "toggle_mute", lambda m: {}, 0.9)
    add(r"^(volume\s+up|louder|increase\s+volume)$",
        "volume_up", lambda m: {}, 0.9)
    add(r"^(volume\s+down|quieter|decrease\s+volume)$",
        "volume_down", lambda m: {}, 0.9)

    # ── Media ────────────────────────────────────────────────────
    add(r"^(play|pause|resume|toggle\s+play)$",
        "media_play_pause", lambda m: {}, 0.85)

    # ── WiFi ─────────────────────────────────────────────────────
    add(r"^(list|show)\s+(wifi|wi-fi|wireless)\s+(profiles?|networks?)$",
        "list_wifi_profiles", lambda m: {}, 0.9)

    # ── Services ─────────────────────────────────────────────────
    add(r"^(list|show)\s+(windows\s+)?services?$",
        "list_services", lambda m: {}, 0.9)

    # ── Display ──────────────────────────────────────────────────
    add(r"^(get|show|check)\s+(display|screen|monitor)\s*(settings?|info|resolution)?$",
        "get_display_settings", lambda m: {}, 0.9)

    # ── Network ──────────────────────────────────────────────────
    add(r"^(list|show)\s+(network\s+)?adapters?$",
        "list_network_adapters", lambda m: {}, 0.9)

    # ── Recycle Bin ──────────────────────────────────────────────
    add(r"^(show|list|display|what('s| is))\s+(in\s+)?(the\s+)?recycle\s*bin$",
        "list_recycle_bin", lambda m: {}, 0.9)
    add(r"^(empty|clear|clean)\s+(the\s+)?recycle\s*bin$",
        "empty_recycle_bin", lambda m: {}, 0.9)

    return patterns


# Module-level pattern cache
_PATTERNS: list[tuple[re.Pattern, str, callable, float]] | None = None


def _get_patterns():
    global _PATTERNS
    if _PATTERNS is None:
        _PATTERNS = _build_patterns()
    return _PATTERNS


# ── Fast-path matching ──────────────────────────────────────────────────

def try_fast_path(goal_description: str) -> FastPathMatch | None:
    """Try to match a goal directly to a tool call.

    Returns a FastPathMatch if confidence is high enough, None otherwise.
    """
    text = goal_description.strip().rstrip(".!?;:")
    if not text:
        return None

    patterns = _get_patterns()
    best_match: FastPathMatch | None = None

    for regex, tool_name, args_fn, confidence in patterns:
        m = regex.match(text)
        if m:
            if confidence >= 0.85:
                # High confidence — execute directly
                try:
                    args = args_fn(m)
                except Exception:
                    args = {}
                match = FastPathMatch(
                    tool_name=tool_name,
                    tool_args=args,
                    confidence=confidence,
                    reasoning=f"Pattern matched: {regex.pattern[:50]}",
                )
                if best_match is None or confidence > best_match.confidence:
                    best_match = match

    # Also check experience cache for past successful single-tool goals
    if best_match is None:
        exp_match = _match_from_experience(text)
        if exp_match and exp_match.confidence >= 0.8:
            best_match = exp_match

    if best_match and best_match.confidence >= 0.85:
        logger.info(
            "Fast-path match: '%s' → %s (confidence=%.2f)",
            text[:50], best_match.tool_name, best_match.confidence,
        )
        return best_match

    return None


def _match_from_experience(goal_description: str) -> FastPathMatch | None:
    """Try to match a goal from past experience patterns.

    If a past goal with the same description used exactly one tool
    successfully, we can skip the LLM and reuse that tool directly.
    """
    try:
        from dash_backend.autonomous.experience import get_experience_cache
        cache = get_experience_cache()

        # Look for exact or close matches in the cache
        for exp in cache._experiences:
            if not exp.success:
                continue
            # Check if goal descriptions are similar
            desc_lower = goal_description.lower()
            exp_lower = exp.goal_description.lower()
            # Use word-boundary match to avoid 'lock' matching 'unlock'
            if (desc_lower == exp_lower
                    or re.search(r"\b" + re.escape(desc_lower) + r"\b", exp_lower)
                    or re.search(r"\b" + re.escape(exp_lower) + r"\b", desc_lower)):
                # Check if only one tool was used
                successful_tools = [t for t in exp.tool_sequence if t.get("success")]
                if len(successful_tools) == 1:
                    tool = successful_tools[0]
                    return FastPathMatch(
                        tool_name=tool["tool"],
                        tool_args=tool.get("args", {}),
                        confidence=0.85,
                        reasoning=f"Experience match: '{exp.goal_description[:50]}'",
                    )
    except Exception:
        pass

    return None
