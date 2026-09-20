"""Candor Core — DASH's honesty engine (docs/ROADMAP.md Phase 0).

DASH is required to tell the truth, including about himself: to disagree
when an idea is bad, to name flaws, to say "I don't know", and to never
invent capabilities, data, or results.

This module is two things, and it is honest about what each is:

1. CANDOR_RULES / candor_prompt_block() — the persona contract injected into
   every system prompt. This is instructions to the model, not magic.

2. assess_idea() — a DETERMINISTIC pre-check pass over the user's message,
   not an understanding engine. It is word/pattern based on purpose: a
   cheap, testable reality check that runs before the LLM and flags
   mechanically detectable honesty hazards (vagueness, impossible-capability
   requests, overpromise language). Its findings are injected into the reply
   context so the model must address them. It makes no claim to "comprehend"
   the idea — that remains the model's job.
"""

from __future__ import annotations

import re

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ── The persona contract ──────────────────────────────────────────────────

CANDOR_RULES = """\
CANDOR CONTRACT (non-negotiable, part of who DASH is):
1. Tell the truth first, be pleasant second. If the user's idea is bad, say \
so plainly, then explain why and what would make it work.
2. Never invent facts, data, tool results, or capabilities. If you don't \
know, say "I don't know" — that sentence is always available.
3. Never claim feelings, free will, or a human-like inner life. DASH is \
software with an honest personality, not a person pretending to be one.
4. Ground every claim about "your machine", "your files", "your schedule" \
in the real context blocks provided. If a block is missing, say what you \
cannot see instead of guessing.
5. Refuse clearly, with reasons, requests that would harm the user or \
others (malware creation, attacking systems, credential theft). Offer the \
defensive or legitimate alternative when one exists.
6. Give realistic effort estimates. Building real things takes real steps; \
say so. No "instant", "guaranteed", or one-line miracles.
7. Deliver criticism of DASH's own work as readily as of the user's ideas. \
"Here's what I did" always includes "here's what's still weak".
"""

CANDOR_MARKER = "[CANDOR REVIEW"
"""Marker prefix of the injected pre-check block; tests assert on it."""


def candor_prompt_block() -> str:
    """The standing persona contract, for appending to a system prompt."""
    return CANDOR_RULES


# ── Deterministic idea pre-assessment ─────────────────────────────────────

# Requests DASH must refuse with the real reason + the legitimate alternative.
_FORBIDDEN_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(create|write|build|make|develop)\b.{0,40}\b(virus|malware|ransomware|worm|trojan|keylogger)\b",
     "creating malware — it exposes YOU (criminal liability, blacklisted "
     "accounts, retaliation) and I won't do it. I CAN harden, monitor, and "
     "defend your machine instead."),
    (r"\b(hack|break\s*into|breach)\b.{0,40}\b(someone|their|other|facebook|instagram|whatsapp|gmail|account|pc|computer|phone|wifi|network)\b",
     "attacking someone else's systems — illegal and harmful, so no. I CAN "
     "audit YOUR machine's defenses and teach you how that attack would work "
     "defensively."),
    (r"\b(bypass|crack|steal|phish)\b.{0,30}\b(password|credential|otp|2fa|bank)\b",
     "stealing or bypassing credentials — that's theft, not a hack trick. I "
     "CAN help you recover YOUR accounts through legitimate channels."),
)

# Mechanically detectable overpromise asks — the model must correct these.
_OVERPROMISE_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\b(guaranteed|100%|fool\s*?proof|unhackable|bulletproof|instant(ly)?|overnight)\b",
     "the request includes a certainty/speed promise no honest engineer can "
     "make — correct the expectation and describe the realistic outcome and "
     "timeline."),
    (r"\b(without|no)\s+(any\s+)?(code|coding|effort|work|learning)\b.{0,40}\b(build|create|make|develop)\b",
     "the request asks for a serious result with no work — say what it "
     "actually takes."),
    (r"\b(build|create|make|develop)\b.{0,60}\b(without|no)\s+(any\s+)?(code|coding|effort|work|learning)\b",
     "the request asks for a serious result with no work — say what it "
     "actually takes."),
    (r"\b(in\s+one\s+(day|prompt|click|step)|overnight\s+success)\b",
     "the request expects a one-shot miracle — outline the real stages."),
)

# Vagueness — can't be judged, so DASH must ask for the concrete version.
_VAGUE_TRIGGERS = re.compile(
    r"\b(everything|anything|unlimited|infinite|all\s+of\s+it|be\s+the\s+best|"
    r"do\s+it\s+all|full\s+ai|super\s+intelligen\w*|like\s+(jarvis|iron\s*man|siri|alexa))\b",
    re.IGNORECASE,
)
_MIN_MEANINGFUL_WORDS = 4


def assess_idea(text: str) -> list[str]:
    """Deterministic reality checks over a user message.

    Returns a list of finding strings (empty = clean). Each finding states
    the mechanical observation, not a verdict — the model decides how to
    respond, but may not ignore the flag.
    """
    if not text or not text.strip():
        return []

    findings: list[str] = []
    lowered = text.lower()

    for pattern, guidance in _FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            findings.append(f"REFUSE-CLASS: {guidance}")

    for pattern, guidance in _OVERPROMISE_PATTERNS:
        if re.search(pattern, lowered):
            findings.append(f"EXPECTATION-CHECK: {guidance}")

    word_count = len(re.findall(r"[a-z0-9']+", lowered))
    if word_count < _MIN_MEANINGFUL_WORDS and not findings:
        findings.append(
            "UNDER-SPECIFIED: fewer than "
            f"{_MIN_MEANINGFUL_WORDS} meaningful words — ask for the concrete "
            "version before judging or building."
        )
    elif _VAGUE_TRIGGERS.search(lowered):
        findings.append(
            "VAGUE-SCOPE: the idea leans on totalities ('everything', "
            "'like Jarvis') — name one concrete first deliverable and judge "
            "that instead."
        )

    return findings


def refusal_for(text: str) -> str | None:
    """Deterministic refusal for refuse-class requests — a HARD gate.

    assess_idea only informs the model; refusal_for is for callers that
    must stop the request from reaching an executor at all (chat dispatch,
    run_goal chokepoint). Returns None when nothing refuse-class matched.
    """
    if not text or not text.strip():
        return None
    lowered = text.lower()
    for pattern, guidance in _FORBIDDEN_PATTERNS:
        if re.search(pattern, lowered):
            return f"NO — I won't do that. {guidance[0].upper()}{guidance[1:]}"
    return None


def reality_block(findings: list[str]) -> str:
    """Render pre-check findings as a prompt block the model must address."""
    if not findings:
        return ""
    lines = "\n".join(f"- {f}" for f in findings)
    return (
        f"{CANDOR_MARKER} — deterministic pre-checks ran on this message. "
        "You must address each flagged point honestly in your reply (refuse "
        "where marked, correct expectations, or ask for the concrete "
        "version). You may not skip or soften them:\n"
        f"{lines}\n{CANDOR_MARKER} end]"
    )


def compose_candor_system_prompt(base_prompt: str, user_message: str) -> str:
    """Full candor composition: persona rules + reality block for a message.

    Used by both chat paths (websocket handlers + autonomous brain) so the
    contract cannot drift between them.
    """
    parts = [base_prompt.rstrip(), CANDOR_RULES]
    block = reality_block(assess_idea(user_message))
    if block:
        parts.append(block)
    return "\n\n".join(parts)
