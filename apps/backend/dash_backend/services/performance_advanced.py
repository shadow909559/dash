"""Advanced performance: HTTP pool, load balancer, feature flags, A/B testing."""
from __future__ import annotations

import hashlib
import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class HTTPConnectionPool:
    """Manage HTTP connection pools for external services."""

    def __init__(self) -> None:
        self._pools: dict[str, dict] = {}

    def create_pool(self, name: str, base_url: str, max_connections: int = 10, timeout: float = 30.0) -> dict:
        self._pools[name] = {"base_url": base_url, "max_connections": max_connections, "timeout": timeout, "active": 0, "idle": max_connections, "total_created": 0, "total_reused": 0, "errors": 0}
        return {"ok": True, "pool": self._pools[name]}

    def acquire(self, pool_name: str) -> dict:
        pool = self._pools.get(pool_name)
        if not pool:
            return {"ok": False, "reason": "Pool not found"}
        if pool["idle"] > 0:
            pool["idle"] -= 1
            pool["active"] += 1
            pool["total_reused"] += 1
            return {"ok": True, "reused": True}
        if pool["active"] < pool["max_connections"]:
            pool["active"] += 1
            pool["total_created"] += 1
            return {"ok": True, "reused": False}
        pool["errors"] += 1
        return {"ok": False, "reason": "Pool exhausted"}

    def release(self, pool_name: str) -> dict:
        pool = self._pools.get(pool_name)
        if pool and pool["active"] > 0:
            pool["active"] -= 1
            pool["idle"] += 1
            return {"ok": True}
        return {"ok": False}

    def get_stats(self) -> dict:
        return {name: {k: v for k, v in p.items() if k != "base_url"} for name, p in self._pools.items()}

    def remove_pool(self, name: str) -> dict:
        self._pools.pop(name, None)
        return {"ok": True}


class LoadBalancer:
    """Distribute requests across multiple backends."""

    def __init__(self) -> None:
        self._backends: list[dict] = []
        self._strategy = "round_robin"
        self._index = 0
        self._health: dict[str, dict] = {}

    def add_backend(self, url: str, weight: int = 1) -> dict:
        backend = {"url": url, "weight": weight, "requests": 0, "errors": 0}
        self._backends.append(backend)
        self._health[url] = {"healthy": True, "last_check": time.time(), "latency_ms": 0}
        return {"ok": True, "backend": backend}

    def remove_backend(self, url: str) -> dict:
        self._backends = [b for b in self._backends if b["url"] != url]
        self._health.pop(url, None)
        return {"ok": True}

    def set_strategy(self, strategy: str) -> dict:
        if strategy not in ("round_robin", "random", "least_connections", "weighted"):
            return {"ok": False, "reason": "Unknown strategy"}
        self._strategy = strategy
        return {"ok": True, "strategy": strategy}

    def get_next(self) -> dict:
        healthy = [b for b in self._backends if self._health.get(b["url"], {}).get("healthy", True)]
        if not healthy:
            return {"ok": False, "reason": "No healthy backends"}
        if self._strategy == "round_robin":
            backend = healthy[self._index % len(healthy)]
            self._index += 1
        elif self._strategy == "random":
            backend = random.choice(healthy)
        elif self._strategy == "least_connections":
            backend = min(healthy, key=lambda b: b["requests"])
        elif self._strategy == "weighted":
            total = sum(b["weight"] for b in healthy)
            r = random.uniform(0, total)
            cumulative = 0
            backend = healthy[0]
            for b in healthy:
                cumulative += b["weight"]
                if r <= cumulative:
                    backend = b
                    break
        else:
            backend = healthy[0]
        backend["requests"] += 1
        return {"ok": True, "url": backend["url"], "strategy": self._strategy}

    def record_error(self, url: str) -> None:
        for b in self._backends:
            if b["url"] == url:
                b["errors"] += 1

    def health_check(self, url: str, healthy: bool, latency_ms: float = 0) -> None:
        self._health[url] = {"healthy": healthy, "last_check": time.time(), "latency_ms": latency_ms}

    def get_backends(self) -> list[dict]:
        return [{**b, "health": self._health.get(b["url"], {})} for b in self._backends]

    def get_stats(self) -> dict:
        return {"strategy": self._strategy, "backends": len(self._backends), "healthy": sum(1 for h in self._health.values() if h.get("healthy"))}


class FeatureFlagService:
    """Toggle features without redeployment."""

    def __init__(self) -> None:
        self._flags: dict[str, dict] = {
            "voice_commands": {"enabled": True, "rollout_percentage": 100, "description": "Voice command support"},
            "browser_automation": {"enabled": True, "rollout_percentage": 100, "description": "Browser automation features"},
            "plugin_marketplace": {"enabled": True, "rollout_percentage": 100, "description": "Plugin marketplace"},
            "knowledge_graph": {"enabled": True, "rollout_percentage": 100, "description": "Knowledge graph visualization"},
            "prompt_studio": {"enabled": True, "rollout_percentage": 100, "description": "Prompt engineering studio"},
            "workflow_builder": {"enabled": True, "rollout_percentage": 100, "description": "Visual workflow builder"},
            "model_ensemble": {"enabled": True, "rollout_percentage": 100, "description": "Multi-model ensemble"},
            "conversation_branching": {"enabled": True, "rollout_percentage": 100, "description": "Conversation forking and comparison"},
            "email_integration": {"enabled": True, "rollout_percentage": 100, "description": "Email read/send integration"},
            "calendar_sync": {"enabled": True, "rollout_percentage": 100, "description": "Calendar synchronization"},
            "encrypted_messaging": {"enabled": True, "rollout_percentage": 100, "description": "E2E encrypted messaging"},
            "2fa_totp": {"enabled": True, "rollout_percentage": 100, "description": "TOTP two-factor auth"},
            "password_vault": {"enabled": True, "rollout_percentage": 100, "description": "Encrypted password storage"},
            "collaboration": {"enabled": True, "rollout_percentage": 100, "description": "Multi-user collaboration"},
        }

    def is_enabled(self, flag_name: str, user_id: str = "") -> bool:
        flag = self._flags.get(flag_name)
        if not flag or not flag.get("enabled"):
            return False
        rollout = flag.get("rollout_percentage", 100)
        if rollout >= 100:
            return True
        if user_id:
            hash_val = int(hashlib.md5(f"{flag_name}:{user_id}".encode()).hexdigest()[:8], 16) % 100
            return hash_val < rollout
        return random.randint(0, 99) < rollout

    def set_flag(self, flag_name: str, enabled: bool, rollout: int = 100, description: str = "") -> dict:
        self._flags[flag_name] = {"enabled": enabled, "rollout_percentage": max(0, min(100, rollout)), "description": description or self._flags.get(flag_name, {}).get("description", "")}
        return {"ok": True, "flag": self._flags[flag_name]}

    def get_all(self) -> dict:
        return dict(self._flags)

    def get_enabled(self) -> list[str]:
        return [name for name, f in self._flags.items() if f.get("enabled")]

    def delete_flag(self, flag_name: str) -> dict:
        self._flags.pop(flag_name, None)
        return {"ok": True}


class ABTestingService:
    """A/B testing infrastructure for features and prompts."""

    def __init__(self) -> None:
        self._experiments: list[dict] = []

    def create_experiment(self, name: str, variants: list[dict], metric: str = "conversion") -> dict:
        exp = {"id": f"exp_{len(self._experiments)}", "name": name, "variants": variants, "metric": metric, "status": "running", "results": {v["name"]: {"assignments": 0, "conversions": 0, "total_value": 0} for v in variants}, "created_at": datetime.now(timezone.utc).isoformat()}
        self._experiments.append(exp)
        return {"ok": True, "experiment": exp}

    def assign_variant(self, experiment_id: str, user_id: str) -> dict:
        exp = next((e for e in self._experiments if e["id"] == experiment_id), None)
        if not exp or exp["status"] != "running":
            return {"ok": False, "reason": "Experiment not found or not running"}
        idx = int(hashlib.md5(f"{experiment_id}:{user_id}".encode()).hexdigest()[:8], 16) % len(exp["variants"])
        variant = exp["variants"][idx]
        exp["results"][variant["name"]]["assignments"] += 1
        return {"ok": True, "variant": variant["name"]}

    def record_conversion(self, experiment_id: str, variant_name: str, value: float = 1.0) -> dict:
        exp = next((e for e in self._experiments if e["id"] == experiment_id), None)
        if not exp:
            return {"ok": False}
        if variant_name in exp["results"]:
            exp["results"][variant_name]["conversions"] += 1
            exp["results"][variant_name]["total_value"] += value
        return {"ok": True}

    def get_results(self, experiment_id: str) -> dict:
        exp = next((e for e in self._experiments if e["id"] == experiment_id), None)
        if not exp:
            return {"ok": False}
        results = {}
        for v_name, data in exp["results"].items():
            rate = data["conversions"] / max(data["assignments"], 1)
            avg_value = data["total_value"] / max(data["conversions"], 1)
            results[v_name] = {"assignments": data["assignments"], "conversions": data["conversions"], "conversion_rate": round(rate, 4), "avg_value": round(avg_value, 2)}
        return {"ok": True, "experiment": exp["name"], "metric": exp["metric"], "results": results}

    def stop_experiment(self, experiment_id: str) -> dict:
        for e in self._experiments:
            if e["id"] == experiment_id:
                e["status"] = "completed"
                return {"ok": True}
        return {"ok": False}

    def get_experiments(self) -> list[dict]:
        return list(self._experiments)


http_pool = HTTPConnectionPool()
load_balancer = LoadBalancer()
feature_flags = FeatureFlagService()
ab_testing = ABTestingService()
