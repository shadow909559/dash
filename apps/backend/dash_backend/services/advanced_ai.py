"""Advanced AI: prompt engineering, model evaluation, learning, multi-modal, curriculum."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PromptStudio:
    """Prompt engineering: versioning, A/B testing, templates."""

    def __init__(self) -> None:
        self._prompts: list[dict] = []
        self._templates: list[dict] = [
            {"id": "tpl_summarize", "name": "Summarize", "template": "Summarize the following text concisely:\n\n{text}", "category": "content"},
            {"id": "tpl_code_review", "name": "Code Review", "template": "Review this code for bugs, performance, and style:\n\n```{language}\n{code}\n```", "category": "code"},
            {"id": "tpl_explain", "name": "Explain", "template": "Explain the following concept clearly and simply:\n\n{concept}", "category": "education"},
            {"id": "tpl_translate", "name": "Translate", "template": "Translate the following text to {language}:\n\n{text}", "category": "content"},
            {"id": "tpl_brainstorm", "name": "Brainstorm", "template": "Generate 10 creative ideas for: {topic}\nBe specific and actionable.", "category": "creative"},
            {"id": "tpl_email", "name": "Email Draft", "template": "Write a professional email to {recipient} about {topic}. Tone: {tone}.", "category": "communication"},
            {"id": "tpl_data_analysis", "name": "Data Analysis", "template": "Analyze this data and provide insights:\n\n{data}\n\nFocus on patterns, anomalies, and recommendations.", "category": "analytics"},
            {"id": "tpl_bug_fix", "name": "Bug Fix", "template": "I'm getting this error:\n\n{error}\n\nIn this code:\n```{language}\n{code}\n```\n\nWhat's wrong and how do I fix it?", "category": "code"},
        ]
        self._ab_tests: list[dict] = []

    def create_prompt(self, name: str, content: str, category: str = "custom",
                      variables: list[str] | None = None, tags: list[str] | None = None) -> dict:
        prompt = {"id": f"prompt_{len(self._prompts)}", "name": name, "content": content,
                  "category": category, "variables": variables or [], "tags": tags or [],
                  "version": 1, "versions": [{"v": 1, "content": content, "created_at": datetime.now(timezone.utc).isoformat()}],
                  "usage_count": 0, "avg_score": 0.0, "created_at": datetime.now(timezone.utc).isoformat()}
        self._prompts.append(prompt)
        return {"ok": True, "prompt": prompt}

    def update_prompt(self, prompt_id: str, new_content: str) -> dict:
        for p in self._prompts:
            if p["id"] == prompt_id:
                p["version"] += 1
                p["content"] = new_content
                p["versions"].append({"v": p["version"], "content": new_content, "created_at": datetime.now(timezone.utc).isoformat()})
                return {"ok": True, "prompt": p}
        return {"ok": False, "reason": "Prompt not found"}

    def get_templates(self, category: Optional[str] = None) -> list[dict]:
        if category:
            return [t for t in self._templates if t["category"] == category]
        return self._templates

    def get_all(self) -> list[dict]:
        return self._prompts

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [p for p in self._prompts if q in p.get("name", "").lower() or q in p.get("content", "").lower()]

    def score_prompt(self, prompt_id: str, score: float) -> dict:
        for p in self._prompts:
            if p["id"] == prompt_id:
                p["usage_count"] += 1
                total = p["avg_score"] * (p["usage_count"] - 1) + score
                p["avg_score"] = round(total / p["usage_count"], 2)
                return {"ok": True, "avg_score": p["avg_score"]}
        return {"ok": False, "reason": "Prompt not found"}

    def create_ab_test(self, name: str, prompt_a_id: str, prompt_b_id: str) -> dict:
        test = {"id": f"ab_{len(self._ab_tests)}", "name": name, "prompt_a": prompt_a_id, "prompt_b": prompt_b_id,
                "results_a": {"count": 0, "total_score": 0}, "results_b": {"count": 0, "total_score": 0},
                "status": "running", "created_at": datetime.now(timezone.utc).isoformat()}
        self._ab_tests.append(test)
        return {"ok": True, "test": test}

    def get_ab_tests(self) -> list[dict]:
        return self._ab_tests


class ModelEvaluator:
    """Benchmark and evaluate model performance."""

    def __init__(self) -> None:
        self._evaluations: list[dict] = []
        self._benchmarks: dict[str, dict] = {
            "accuracy": {"description": "Correctness of responses", "weight": 0.3},
            "relevance": {"description": "How well response addresses the query", "weight": 0.25},
            "creativity": {"description": "Originality and novel thinking", "weight": 0.1},
            "speed": {"description": "Response latency", "weight": 0.15},
            "cost_efficiency": {"description": "Quality per dollar", "weight": 0.1},
            "safety": {"description": "Absence of harmful content", "weight": 0.1},
        }

    def evaluate(self, model_id: str, query: str, response: str, scores: dict[str, float]) -> dict:
        weighted_total = 0.0
        for metric, score in scores.items():
            weight = self._benchmarks.get(metric, {}).get("weight", 0.1)
            weighted_total += score * weight
        evaluation = {"id": f"eval_{len(self._evaluations)}", "model_id": model_id, "query": query[:200],
                      "response_preview": response[:200], "scores": scores, "weighted_score": round(weighted_total, 3),
                      "timestamp": datetime.now(timezone.utc).isoformat()}
        self._evaluations.append(evaluation)
        return {"ok": True, "evaluation": evaluation}

    def get_leaderboard(self) -> list[dict]:
        model_scores: dict[str, list[float]] = {}
        for e in self._evaluations:
            mid = e["model_id"]
            model_scores.setdefault(mid, []).append(e["weighted_score"])
        return sorted([{"model_id": m, "avg_score": round(sum(s) / len(s), 3), "evaluations": len(s)}
                        for m, s in model_scores.items()], key=lambda x: x["avg_score"], reverse=True)

    def get_benchmarks(self) -> dict:
        return dict(self._benchmarks)

    def get_model_stats(self, model_id: str) -> dict:
        evals = [e for e in self._evaluations if e.get("model_id") == model_id]
        if not evals:
            return {"model_id": model_id, "evaluations": 0}
        scores = [e["weighted_score"] for e in evals]
        return {"model_id": model_id, "evaluations": len(evals), "avg_score": round(sum(scores) / len(scores), 3),
                "min_score": round(min(scores), 3), "max_score": round(max(scores), 3)}


class LearningService:
    """Learning from corrections, skill acquisition, active learning."""

    def __init__(self) -> None:
        self._corrections: list[dict] = []
        self._skills: list[dict] = []
        self._learned_patterns: list[dict] = []

    def record_correction(self, original_response: str, corrected_response: str, context: str = "",
                          user_id: str = "system") -> dict:
        correction = {"id": f"corr_{len(self._corrections)}", "original": original_response[:500],
                      "corrected": corrected_response[:500], "context": context[:500], "user_id": user_id,
                      "timestamp": datetime.now(timezone.utc).isoformat()}
        self._corrections.append(correction)
        return {"ok": True, "correction": correction}

    def get_corrections(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._corrections[-limit:]))

    def acquire_skill(self, name: str, description: str, examples: list[dict]) -> dict:
        skill = {"id": f"skill_{len(self._skills)}", "name": name, "description": description,
                 "examples": examples, "confidence": 0.5, "usage_count": 0,
                 "created_at": datetime.now(timezone.utc).isoformat()}
        self._skills.append(skill)
        return {"ok": True, "skill": skill}

    def get_skills(self) -> list[dict]:
        return self._skills

    def use_skill(self, skill_id: str, success: bool = True) -> dict:
        for s in self._skills:
            if s["id"] == skill_id:
                s["usage_count"] += 1
                if success:
                    s["confidence"] = min(1.0, s["confidence"] + 0.05)
                else:
                    s["confidence"] = max(0.0, s["confidence"] - 0.1)
                return {"ok": True, "confidence": s["confidence"]}
        return {"ok": False, "reason": "Skill not found"}

    def record_pattern(self, pattern: str, context: str, success: bool) -> dict:
        self._learned_patterns.append({"pattern": pattern, "context": context, "success": success,
                                        "timestamp": datetime.now(timezone.utc).isoformat()})
        return {"ok": True}

    def get_stats(self) -> dict:
        return {"corrections": len(self._corrections), "skills": len(self._skills),
                "patterns_learned": len(self._learned_patterns),
                "avg_skill_confidence": round(sum(s["confidence"] for s in self._skills) / max(len(self._skills), 1), 2)}


prompt_studio = PromptStudio()
model_evaluator = ModelEvaluator()
learning_service = LearningService()
