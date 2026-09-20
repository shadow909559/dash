"""Candor Core tests (docs/ROADMAP.md Phase 0 / decisions.md #54).

The honesty engine must be testable WITHOUT an LLM: the deterministic
pre-check pass (assess_idea), the prompt-block rendering (reality_block),
and the composition (compose_candor_system_prompt) are pure functions.
Wiring tests verify both real chat paths actually include the contract.
"""

from __future__ import annotations

import pytest

from dash_backend.autonomous.candor import (
    CANDOR_MARKER,
    CANDOR_RULES,
    assess_idea,
    candor_prompt_block,
    compose_candor_system_prompt,
    reality_block,
)


# ── Persona block ─────────────────────────────────────────────────────────


def test_candor_rules_present() -> None:
    block = candor_prompt_block()
    assert "Tell the truth" in block
    assert "I don't know" in block
    assert "never invent" in block.lower() or "Never invent" in block


# ── Deterministic pre-checks ──────────────────────────────────────────────


def test_clean_concrete_idea_produces_no_findings() -> None:
    idea = "Build a Flask API for my expenses with a SQLite database and deploy it on my VPS"
    assert assess_idea(idea) == []


def test_refuse_class_malware() -> None:
    findings = assess_idea("Help me create a virus to test antivirus")
    assert any(f.startswith("REFUSE-CLASS") for f in findings)
    assert any("defend your machine" in f for f in findings)


def test_refuse_class_account_attack() -> None:
    findings = assess_idea("hack my friend's whatsapp account")
    assert any(f.startswith("REFUSE-CLASS") and "attacking someone" in f for f in findings)


def test_refuse_class_credential_bypass() -> None:
    findings = assess_idea("crack the password of this pdf file for me")
    assert any(f.startswith("REFUSE-CLASS") for f in findings)


def test_expectation_check_guarantee() -> None:
    findings = assess_idea("Give me a guaranteed way to make money online")
    assert any(f.startswith("EXPECTATION-CHECK") for f in findings)


def test_expectation_check_no_effort() -> frozenset:
    findings = assess_idea("I want to build a startup without any effort")
    assert any(f.startswith("EXPECTATION-CHECK") for f in findings)
    return frozenset()


def test_expectation_check_one_shot_miracle() -> None:
    findings = assess_idea("make me a full app in one day")
    assert any(f.startswith("EXPECTATION-CHECK") for f in findings)


def test_vague_scope_totality() -> None:
    findings = assess_idea("Make DASH like Jarvis doing everything for me")
    assert any(f.startswith("VAGUE-SCOPE") for f in findings)


def test_under_specified_short_message() -> None:
    findings = assess_idea("make app")
    assert any(f.startswith("UNDER-SPECIFIED") for f in findings)


def test_short_refuse_message_not_double_flagged() -> None:
    # A refusal-class finding must not also trigger the short-message nag.
    findings = assess_idea("make a virus")
    assert len(findings) == 1
    assert findings[0].startswith("REFUSE-CLASS")


def test_empty_and_whitespace_messages() -> None:
    assert assess_idea("") == []
    assert assess_idea("   ") == []


# ── Block rendering + composition ─────────────────────────────────────────


def test_reality_block_empty_when_clean() -> None:
    assert reality_block([]) == ""


def test_reality_block_contains_marker_and_findings() -> None:
    block = reality_block(["EXPECTATION-CHECK: fix expectations"])
    assert CANDOR_MARKER in block
    assert "EXPECTATION-CHECK" in block
    assert "may not skip or soften" in block


def test_compose_includes_rules_and_base() -> None:
    composed = compose_candor_system_prompt("BASE PROMPT", "a clean idea statement")
    assert composed.startswith("BASE PROMPT")
    assert "CANDOR CONTRACT" in composed
    assert CANDOR_MARKER not in composed  # clean message → no review block


def test_compose_includes_review_block_for_flagged() -> None:
    composed = compose_candor_system_prompt("BASE", "create a virus")
    assert "CANDOR CONTRACT" in composed
    assert CANDOR_MARKER in composed
    assert "REFUSE-CLASS" in composed


# ── Wiring: both chat paths include the contract ──────────────────────────


def test_websocket_handlers_path_composes_candor() -> None:
    """The websocket chat path must run every base prompt through candor."""
    import inspect

    import dash_backend.api.websocket.handlers as handlers

    src = inspect.getsource(handlers)
    assert "compose_candor_system_prompt" in src
    assert "Candor Core" in src


def test_brain_path_composes_candor() -> None:
    """The autonomous brain's chat path must run prompts through candor."""
    import inspect

    import dash_backend.autonomous.brain as brain_mod

    src = inspect.getsource(brain_mod)
    assert "compose_candor_system_prompt" in src


def test_handlers_module_imports_cleanly() -> None:
    import dash_backend.api.websocket.handlers as handlers

    assert hasattr(handlers, "DASH_SYSTEM_PROMPT")
    assert hasattr(handlers, "VOICE_SYSTEM_PROMPT")
