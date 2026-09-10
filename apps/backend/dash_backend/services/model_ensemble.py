"""Multi-model ensemble, model hot-swap, confidence scoring, and conversation branching."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ModelEnsemble:
    """Run multiple models simultaneously and compare outputs."""

    def __init__(self) -> None:
        self._strategies: dict[str, dict] = {
            "best_of_n": {"description": "Run N models, pick the highest-scored response", "default_n": 3},
            "vote": {"description": "Run N models, majority vote on answer", "default_n": 3},
            "cascade": {"description": "Try cheap model first, escalate if low confidence", "threshold": 0.7},
            "blend": {"description": "Combine responses using weighted average", "weights": {}},
        }
        self._active_strategy: str = "cascade"
        self._model_weights: dict[str, float] = {"openai": 0.9, "anthropic": 0.85, "groq": 0.7, "ollama": 0.6, "deepseek": 0.75}
        self._ensemble_history: list[dict] = []

    def get_config(self) -> dict:
        return {
            "active_strategy": self._active_strategy,
            "strategies": self._strategies,
            "model_weights": self._model_weights,
        }

    def set_strategy(self, strategy: str) -> dict:
        if strategy not in self._strategies:
            return {"ok": False, "reason": f"Unknown strategy. Use: {list(self._strategies.keys())}"}
        self._active_strategy = strategy
        return {"ok": True, "strategy": strategy}

    def set_model_weight(self, model: str, weight: float) -> dict:
        self._model_weights[model] = max(0.0, min(1.0, weight))
        return {"ok": True}

    def record_ensemble_result(self, strategy: str, models_used: list[str],
                                selected_model: str, confidence: float, latency_ms: float) -> None:
        self._ensemble_history.append({
            "strategy": strategy,
            "models_used": models_used,
            "selected_model": selected_model,
            "confidence": confidence,
            "latency_ms": latency_ms,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._ensemble_history) > 500:
            self._ensemble_history = self._ensemble_history[-250:]

    def get_history(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._ensemble_history[-limit:]))

    def get_stats(self) -> dict:
        if not self._ensemble_history:
            return {"total_runs": 0}
        by_model: dict[str, int] = {}
        for h in self._ensemble_history:
            m = h.get("selected_model", "unknown")
            by_model[m] = by_model.get(m, 0) + 1
        avg_confidence = sum(h.get("confidence", 0) for h in self._ensemble_history) / len(self._ensemble_history)
        return {
            "total_runs": len(self._ensemble_history),
            "by_model": by_model,
            "avg_confidence": round(avg_confidence, 3),
        }


class ConfidenceScorer:
    """Score confidence of AI responses based on multiple signals."""

    def __init__(self) -> None:
        self._scores: list[dict] = []

    def score(self, response: str, context: list[str] = None, sources: list[dict] = None) -> dict:
        signals = []

        # Length signal
        word_count = len(response.split())
        length_signal = min(1.0, word_count / 100)
        signals.append({"name": "length", "score": length_signal})

        # Source citation signal
        source_count = len(sources or [])
        source_signal = min(1.0, source_count * 0.3)
        signals.append({"name": "sources", "score": source_signal})

        # Hedging language signal (lower confidence if lots of hedging)
        hedging_words = ["maybe", "perhaps", "possibly", "might", "could", "not sure", "I think"]
        hedging_count = sum(1 for w in hedging_words if w in response.lower())
        hedging_signal = max(0.0, 1.0 - hedging_count * 0.15)
        signals.append({"name": "hedging", "score": hedging_signal})

        # Specificity signal (numbers, proper nouns, technical terms)
        import re
        numbers = len(re.findall(r'\d+', response))
        specificity_signal = min(1.0, numbers * 0.1)
        signals.append({"name": "specificity", "score": specificity_signal})

        # Context relevance signal
        context_signal = 0.7 if context else 0.5
        signals.append({"name": "context", "score": context_signal})

        # Weighted average
        weights = {"length": 0.15, "sources": 0.25, "hedging": 0.2, "specificity": 0.15, "context": 0.25}
        total = sum(s["score"] * weights.get(s["name"], 0.1) for s in signals)

        result = {
            "confidence": round(total, 3),
            "signals": signals,
            "level": "high" if total >= 0.7 else ("medium" if total >= 0.4 else "low"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._scores.append(result)
        if len(self._scores) > 1000:
            self._scores = self._scores[-500:]
        return result

    def get_average_confidence(self, limit: int = 100) -> dict:
        recent = self._scores[-limit:]
        if not recent:
            return {"avg": 0, "count": 0}
        avg = sum(s["confidence"] for s in recent) / len(recent)
        return {"avg": round(avg, 3), "count": len(recent)}

    def get_distribution(self) -> dict:
        high = sum(1 for s in self._scores if s.get("level") == "high")
        medium = sum(1 for s in self._scores if s.get("level") == "medium")
        low = sum(1 for s in self._scores if s.get("level") == "low")
        return {"high": high, "medium": medium, "low": low, "total": len(self._scores)}


class ConversationBranching:
    """Fork and manage conversation branches."""

    def __init__(self) -> None:
        self._branches: dict[str, dict] = {}
        self._branches["main"] = {
            "id": "main",
            "name": "Main",
            "parent_id": None,
            "messages": [],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }

    def fork(self, branch_id: str, from_message_index: int, name: Optional[str] = None) -> dict:
        parent = self._branches.get(branch_id)
        if not parent:
            return {"ok": False, "reason": "Branch not found"}
        new_id = f"branch_{len(self._branches)}"
        forked_messages = list(parent["messages"][:from_message_index])
        new_branch = {
            "id": new_id,
            "name": name or f"Fork from {parent['name']}",
            "parent_id": branch_id,
            "fork_point": from_message_index,
            "messages": forked_messages,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "is_active": True,
        }
        self._branches[new_id] = new_branch
        return {"ok": True, "branch": new_branch}

    def add_message(self, branch_id: str, message: dict) -> dict:
        branch = self._branches.get(branch_id)
        if not branch:
            return {"ok": False, "reason": "Branch not found"}
        message["branch_id"] = branch_id
        message["index"] = len(branch["messages"])
        branch["messages"].append(message)
        return {"ok": True, "message": message}

    def get_branch(self, branch_id: str) -> Optional[dict]:
        return self._branches.get(branch_id)

    def list_branches(self) -> list[dict]:
        return [
            {"id": b["id"], "name": b["name"], "parent_id": b["parent_id"],
             "message_count": len(b["messages"]), "created_at": b["created_at"]}
            for b in self._branches.values()
        ]

    def delete_branch(self, branch_id: str) -> dict:
        if branch_id == "main":
            return {"ok": False, "reason": "Cannot delete main branch"}
        if branch_id not in self._branches:
            return {"ok": False, "reason": "Branch not found"}
        del self._branches[branch_id]
        return {"ok": True}

    def rename_branch(self, branch_id: str, name: str) -> dict:
        branch = self._branches.get(branch_id)
        if not branch:
            return {"ok": False, "reason": "Branch not found"}
        branch["name"] = name
        return {"ok": True}

    def compare(self, branch_a: str, branch_b: str) -> dict:
        a = self._branches.get(branch_a)
        b = self._branches.get(branch_b)
        if not a or not b:
            return {"ok": False, "reason": "Branch not found"}
        a_len = len(a["messages"])
        b_len = len(b["messages"])
        min_len = min(a_len, b_len)
        common = sum(
            1 for i in range(min_len)
            if a["messages"][i].get("content") == b["messages"][i].get("content")
        )
        return {
            "branch_a": {"id": branch_a, "name": a["name"], "messages": a_len},
            "branch_b": {"id": branch_b, "name": b["name"], "messages": b_len},
            "common_messages": common,
            "diverged_at": common,
        }


class ModelHotSwap:
    """Hot-swap AI providers without losing context.

    Active model and swap history persist to the shared local SQLite store.
    """

    def __init__(self, store=None) -> None:
        self._store = store if store is not None else __import__(
            "dash_backend.services.local_store", fromlist=["LocalStore"]
        ).LocalStore.instance()
        self._available_models: list[dict] = [
            {"id": "openai/gpt-4o", "provider": "openai", "name": "GPT-4o", "active": True, "tier": "premium"},
            {"id": "openai/gpt-4o-mini", "provider": "openai", "name": "GPT-4o Mini", "active": True, "tier": "fast"},
            {"id": "anthropic/claude-3.5-sonnet", "provider": "anthropic", "name": "Claude 3.5 Sonnet", "active": True, "tier": "premium"},
            {"id": "anthropic/claude-3-haiku", "provider": "anthropic", "name": "Claude 3 Haiku", "active": True, "tier": "fast"},
            {"id": "deepseek/deepseek-chat", "provider": "deepseek", "name": "DeepSeek Chat", "active": True, "tier": "standard"},
            {"id": "groq/llama-3-70b", "provider": "groq", "name": "Llama 3 70B", "active": True, "tier": "fast"},
            {"id": "ollama/local", "provider": "ollama", "name": "Local Ollama", "active": True, "tier": "local"},
        ]
        self._active_model: str = self._load_active_model()
        self._swap_history: list[dict] = [
            __import__("json").loads(r["data"])
            for r in self._store.query("SELECT data FROM model_swap_history ORDER BY id ASC")
        ]

    def _load_active_model(self) -> str:
        rows = self._store.query("SELECT data FROM kv_settings WHERE key = 'active_model'")
        if rows:
            saved = __import__("json").loads(rows[0]["data"]).get("model")
            if saved in [m["id"] for m in self._available_models]:
                return saved
        return "openai/gpt-4o"

    def get_models(self) -> list[dict]:
        return self._available_models

    def get_active(self) -> str:
        return self._active_model

    def swap(self, model_id: str) -> dict:
        valid = [m["id"] for m in self._available_models]
        if model_id not in valid:
            return {"ok": False, "reason": f"Unknown model. Available: {valid}"}
        old = self._active_model
        self._active_model = model_id
        entry = {
            "from": old,
            "to": model_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._swap_history.append(entry)
        import json as _json
        self._store.execute(
            "INSERT INTO model_swap_history (data) VALUES (?)", (_json.dumps(entry),)
        )
        self._store.execute(
            "INSERT INTO kv_settings (key, data) VALUES ('active_model', ?) "
            "ON CONFLICT(key) DO UPDATE SET data = excluded.data",
            (_json.dumps({"model": model_id}),),
        )
        return {"ok": True, "from": old, "to": model_id}

    def get_history(self) -> list[dict]:
        return list(self._swap_history)

    def toggle_model(self, model_id: str, active: bool) -> dict:
        for m in self._available_models:
            if m["id"] == model_id:
                m["active"] = active
                return {"ok": True}
        return {"ok": False, "reason": "Model not found"}


# Singletons
model_ensemble = ModelEnsemble()
confidence_scorer = ConfidenceScorer()
conversation_branching = ConversationBranching()
model_hotswap = ModelHotSwap()
