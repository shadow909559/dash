"""Distilled Planner — instant task decomposition without LLM.

Uses pattern matching, keyword extraction, and pre-built templates to break
down common tasks in <10ms instead of 30-60s LLM calls.

Architecture:
  1. Classify task type from keywords (code/research/execute/plan)
  2. Extract entities (language, file types, actions)
  3. Match against distilled templates
  4. Generate steps from template + entities
  5. Only fall back to LLM for truly novel tasks

Speed: <10ms for matched patterns, 30-60s for LLM fallback
Coverage: ~70% of common dev tasks matched instantly
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DistilledStep:
    description: str
    step_type: str  # plan, code, research, execute, verify
    agent: str  # planner, coder, researcher, executor, verifier
    confidence: float  # 0-1, how sure we are


@dataclass
class DistilledPlan:
    steps: list[DistilledStep]
    matched_pattern: str | None
    planning_time_ms: float
    used_llm: bool


# ── Pattern Registry ──────────────────────────────────────────

PATTERNS: list[dict[str, Any]] = [
    # Code generation patterns
    {
        "keywords": ["write", "create", "generate", "build", "implement", "code"],
        "file_hints": [".py", ".js", ".ts", ".java", ".go", ".rs", ".sh"],
        "type": "code_gen",
        "template": [
            ("Analyze requirements and design the solution", "plan", "planner"),
            ("Write the implementation code", "code", "coder"),
            ("Add error handling and edge cases", "code", "coder"),
            ("Write tests for the implementation", "code", "coder"),
            ("Verify code compiles and tests pass", "verify", "verifier"),
        ],
    },
    # API/endpoint patterns
    {
        "keywords": ["api", "endpoint", "route", "rest", "graphql", "server"],
        "type": "api_build",
        "template": [
            ("Design API schema and endpoints", "plan", "planner"),
            ("Implement request/response models", "code", "coder"),
            ("Write route handlers with validation", "code", "coder"),
            ("Add authentication and rate limiting", "code", "coder"),
            ("Write API tests", "code", "coder"),
            ("Verify endpoints work correctly", "verify", "verifier"),
        ],
    },
    # Debug/fix patterns
    {
        "keywords": ["debug", "fix", "error", "bug", "issue", "broken", "crash"],
        "type": "debug",
        "template": [
            ("Reproduce and analyze the error", "research", "researcher"),
            ("Identify root cause in code", "code", "coder"),
            ("Implement the fix", "code", "coder"),
            ("Test the fix doesn't break other things", "verify", "verifier"),
        ],
    },
    # Research patterns
    {
        "keywords": ["research", "compare", "analyze", "evaluate", "review", "investigate"],
        "type": "research",
        "template": [
            ("Define research scope and questions", "plan", "planner"),
            ("Gather information from sources", "research", "researcher"),
            ("Analyze and compare findings", "research", "researcher"),
            ("Summarize recommendations", "research", "researcher"),
        ],
    },
    # Deploy patterns
    {
        "keywords": ["deploy", "production", "server", "hosting", "ci/cd", "docker", "nginx"],
        "type": "deploy",
        "template": [
            ("Assess deployment requirements", "plan", "planner"),
            ("Prepare configuration files", "code", "coder"),
            ("Set up infrastructure", "execute", "executor"),
            ("Configure security and monitoring", "code", "coder"),
            ("Verify deployment works", "verify", "verifier"),
        ],
    },
    # Data processing patterns
    {
        "keywords": ["parse", "extract", "transform", "process", "etl", "pipeline", "scrape"],
        "type": "data_pipeline",
        "template": [
            ("Analyze input data format", "plan", "planner"),
            ("Write data extraction logic", "code", "coder"),
            ("Implement transformation rules", "code", "coder"),
            ("Add validation and error handling", "code", "coder"),
            ("Test with sample data", "verify", "verifier"),
        ],
    },
    # Testing patterns
    {
        "keywords": ["test", "unit test", "integration test", "e2e", "coverage"],
        "type": "testing",
        "template": [
            ("Identify test cases and edge cases", "plan", "planner"),
            ("Write unit tests", "code", "coder"),
            ("Write integration tests", "code", "coder"),
            ("Run tests and fix failures", "execute", "executor"),
        ],
    },
    # Refactoring patterns
    {
        "keywords": ["refactor", "restructure", "reorganize", "clean up", "optimize"],
        "type": "refactor",
        "template": [
            ("Analyze current code structure", "research", "researcher"),
            ("Plan refactoring approach", "plan", "planner"),
            ("Implement changes incrementally", "code", "coder"),
            ("Verify behavior is preserved", "verify", "verifier"),
        ],
    },
    # System admin patterns
    {
        "keywords": ["install", "setup", "configure", "update", "migrate", "backup"],
        "type": "sysadmin",
        "template": [
            ("Check prerequisites and dependencies", "plan", "planner"),
            ("Execute setup steps", "execute", "executor"),
            ("Configure settings", "code", "coder"),
            ("Verify installation works", "verify", "verifier"),
        ],
    },
    # Security patterns
    {
        "keywords": ["security", "auth", "encrypt", "ssl", "firewall", "permission"],
        "type": "security",
        "template": [
            ("Assess security requirements", "plan", "planner"),
            ("Research security best practices", "research", "researcher"),
            ("Implement security measures", "code", "coder"),
            ("Test for vulnerabilities", "verify", "verifier"),
        ],
    },
    # ── Database patterns ──────────────────────────────────────
    # Schema design, migrations, queries, optimization, ORM
    {
        "keywords": ["database", "schema", "table", "migration", "query", "sql", "orm", "index"],
        "type": "database",
        "template": [
            ("Analyze data requirements and relationships", "plan", "planner"),
            ("Design database schema with indexes", "code", "coder"),
            ("Write migration scripts", "code", "coder"),
            ("Implement ORM models and queries", "code", "coder"),
            ("Add constraints, triggers, and validation", "code", "coder"),
            ("Test with sample data and check query performance", "verify", "verifier"),
        ],
    },
    # Database optimization patterns
    {
        "keywords": ["slow query", "optimize database", "connection pool", "replication", "sharding", "partition"],
        "type": "db_optimize",
        "template": [
            ("Profile slow queries and identify bottlenecks", "research", "researcher"),
            ("Add indexes and optimize query plans", "code", "coder"),
            ("Implement connection pooling", "code", "coder"),
            ("Set up read replicas or caching layer", "code", "coder"),
            ("Benchmark before and after optimization", "verify", "verifier"),
        ],
    },
    # NoSQL patterns (MongoDB, Redis, DynamoDB)
    {
        "keywords": ["mongodb", "redis", "dynamodb", "nosql", "document store", "cache", "key-value"],
        "type": "nosql",
        "template": [
            ("Choose appropriate NoSQL pattern (document, key-value, graph)", "plan", "planner"),
            ("Design data model for NoSQL access patterns", "code", "coder"),
            ("Implement CRUD operations and indexes", "code", "coder"),
            ("Add caching strategy and TTL policies", "code", "coder"),
            ("Test with realistic data volumes", "verify", "verifier"),
        ],
    },
    # ── Mobile development patterns ────────────────────────────
    # Android (Kotlin), iOS (Swift), Cross-platform (Flutter/RN)
    {
        "keywords": ["android", "kotlin", "jetpack", "compose", "activity", "fragment", "apk"],
        "type": "android",
        "template": [
            ("Design app architecture (MVVM/MVI)", "plan", "planner"),
            ("Create UI screens with Jetpack Compose", "code", "coder"),
            ("Implement data layer (Room/Network)", "code", "coder"),
            ("Add navigation, permissions, and lifecycle handling", "code", "coder"),
            ("Write unit and UI tests", "code", "coder"),
            ("Build APK and test on device/emulator", "execute", "executor"),
        ],
    },
    {
        "keywords": ["ios", "swift", "swiftui", "uikit", "xcode", "iphone", "ipad"],
        "type": "ios",
        "template": [
            ("Design app architecture (MVVM/Clean)", "plan", "planner"),
            ("Create UI views with SwiftUI", "code", "coder"),
            ("Implement data layer (CoreData/Network)", "code", "coder"),
            ("Add navigation and lifecycle handling", "code", "coder"),
            ("Write unit and UI tests", "code", "coder"),
            ("Build and test on simulator/device", "execute", "executor"),
        ],
    },
    {
        "keywords": ["flutter", "dart", "react native", "expo", "cross-platform", "mobile app", "ionic"],
        "type": "cross_platform_mobile",
        "template": [
            ("Choose framework and design app architecture", "plan", "planner"),
            ("Set up project structure and dependencies", "code", "coder"),
            ("Build shared UI components and screens", "code", "coder"),
            ("Implement platform-specific logic", "code", "coder"),
            ("Add state management and API integration", "code", "coder"),
            ("Test on both iOS and Android", "verify", "verifier"),
        ],
    },
    # ── AI/ML patterns ─────────────────────────────────────────
    # Training, fine-tuning, embeddings, pipelines, deployment
    {
        "keywords": ["train", "training", "model", "dataset", "epoch", "loss", "accuracy", "fine-tune", "finetune"],
        "type": "ml_training",
        "template": [
            ("Prepare and clean training dataset", "plan", "planner"),
            ("Design model architecture and hyperparameters", "research", "researcher"),
            ("Write training pipeline with data loading", "code", "coder"),
            ("Implement training loop with logging and checkpoints", "code", "coder"),
            ("Evaluate model on validation set", "execute", "executor"),
            ("Tune hyperparameters and iterate", "verify", "verifier"),
        ],
    },
    {
        "keywords": ["embedding", "vector", "semantic search", "similarity", "rag", "retrieval", "chunking"],
        "type": "ml_embeddings",
        "template": [
            ("Choose embedding model and chunking strategy", "plan", "planner"),
            ("Write document ingestion and chunking pipeline", "code", "coder"),
            ("Implement vector storage and indexing", "code", "coder"),
            ("Build retrieval pipeline with similarity search", "code", "coder"),
            ("Add reranking and context assembly", "code", "coder"),
            ("Test retrieval quality with sample queries", "verify", "verifier"),
        ],
    },
    {
        "keywords": ["lora", "qlora", "gguf", "quantize", "onnx", "tensorrt", "deploy model", "inference"],
        "type": "ml_deploy",
        "template": [
            ("Choose optimization strategy (LoRA/quantization/distillation)", "plan", "planner"),
            ("Apply model optimization and export", "code", "coder"),
            ("Set up inference server with health checks", "code", "coder"),
            ("Implement request batching and caching", "code", "coder"),
            ("Benchmark latency and throughput", "execute", "executor"),
            ("Test end-to-end with production traffic", "verify", "verifier"),
        ],
    },
    {
        "keywords": ["neural network", "deep learning", "cnn", "rnn", "transformer", "diffusion", "gan", "pytorch", "tensorflow"],
        "type": "ml_deep_learning",
        "template": [
            ("Define problem, metrics, and data requirements", "plan", "planner"),
            ("Research architecture choices and benchmarks", "research", "researcher"),
            ("Implement model architecture", "code", "coder"),
            ("Write training pipeline with augmentation", "code", "coder"),
            ("Train, evaluate, and iterate on hyperparameters", "execute", "executor"),
            ("Export model and test inference", "verify", "verifier"),
        ],
    },
    # ── Documentation patterns ─────────────────────────────────
    {
        "keywords": ["document", "readme", "docstring", "swagger", "openapi", "changelog"],
        "type": "documentation",
        "template": [
            ("Identify documentation scope and audience", "plan", "planner"),
            ("Write API documentation with examples", "code", "coder"),
            ("Add inline docstrings and type hints", "code", "coder"),
            ("Create README with setup and usage instructions", "code", "coder"),
        ],
    },
    # ── Performance patterns ───────────────────────────────────
    {
        "keywords": ["performance", "latency", "throughput", "benchmark", "profiling", "memory leak", "cpu usage"],
        "type": "performance",
        "template": [
            ("Profile application and identify bottlenecks", "research", "researcher"),
            ("Implement caching and memoization", "code", "coder"),
            ("Optimize hot paths and reduce allocations", "code", "coder"),
            ("Add monitoring and alerting", "code", "coder"),
            ("Benchmark before and after optimizations", "verify", "verifier"),
        ],
    },
    # ── Monitoring patterns ────────────────────────────────────
    {
        "keywords": ["monitoring", "logging", "alerting", "observability", "metrics", "dashboard", "grafana", "prometheus"],
        "type": "monitoring",
        "template": [
            ("Define SLIs, SLOs, and alert thresholds", "plan", "planner"),
            ("Set up structured logging with correlation IDs", "code", "coder"),
            ("Implement metrics collection and dashboards", "code", "coder"),
            ("Configure alerts and escalation policies", "code", "coder"),
            ("Test alerting with failure scenarios", "verify", "verifier"),
        ],
    },
    # ── CI/CD patterns ─────────────────────────────────────────
    {
        "keywords": ["ci", "cd", "pipeline", "github actions", "gitlab ci", "jenkins", "automated build"],
        "type": "cicd",
        "template": [
            ("Design pipeline stages and triggers", "plan", "planner"),
            ("Write CI workflow with lint, test, build stages", "code", "coder"),
            ("Add CD pipeline with staging and production", "code", "coder"),
            ("Implement caching and parallel jobs", "code", "coder"),
            ("Test pipeline with a feature branch", "verify", "verifier"),
        ],
    },
    # ── CLI tool patterns ──────────────────────────────────────
    {
        "keywords": ["cli", "command line", "terminal", "argument parser", "flag", "subcommand"],
        "type": "cli_tool",
        "template": [
            ("Design CLI interface and subcommands", "plan", "planner"),
            ("Implement argument parsing with help text", "code", "coder"),
            ("Write core logic for each subcommand", "code", "coder"),
            ("Add output formatting and error messages", "code", "coder"),
            ("Write integration tests and man page", "verify", "verifier"),
        ],
    },
]

# ── Language Detection ─────────────────────────────────────────

LANG_PATTERNS = {
    "python": ["python", ".py", "pip", "django", "flask", "fastapi", "uvicorn", "sqlalchemy", "pytest", "celery"],
    "javascript": ["javascript", ".js", "node", "npm", "express", "react", "vue", "svelte"],
    "typescript": ["typescript", ".ts", "tsx", "tsc", "vite", "next.js", "nest.js"],
    "rust": ["rust", ".rs", "cargo", "rustc"],
    "go": ["go", ".go", "golang", "goroutine"],
    "java": ["java", ".java", "spring", "maven", "gradle"],
    "kotlin": ["kotlin", ".kt", "kts", "jetpack", "compose", "android studio", "ktor"],
    "swift": ["swift", ".swift", "swiftui", "uikit", "xcode", "cocoapods"],
    "dart": ["dart", ".dart", "flutter", "pubspec", "dartpad"],
    "bash": ["bash", "shell", "script", ".sh", ".bat", ".ps1"],
    "sql": ["sql", "database", "query", "migration", "schema", "postgresql", "mysql", "sqlite"],
    "yaml": ["yaml", ".yml", "docker", "kubernetes", "k8s"],
    "nginx": ["nginx", "reverse proxy", "upstream", "server block"],
    "python_ml": ["pytorch", "tensorflow", "keras", "sklearn", "numpy", "pandas", "jupyter", "notebook", "huggingface"],
}

# ── Entity Extraction ──────────────────────────────────────────

def extract_entities(task: str) -> dict[str, Any]:
    """Extract language, file types, actions, and complexity from task."""
    task_lower = task.lower()

    # Detect language
    language = None
    for lang, keywords in LANG_PATTERNS.items():
        if any(kw in task_lower for kw in keywords):
            language = lang
            break

    # Detect file types mentioned
    file_types = re.findall(r'\.\w{2,5}', task)

    # Detect complexity indicators
    complexity = "medium"
    complex_signals = ["complex", "advanced", "full", "complete", "production", "enterprise"]
    simple_signals = ["simple", "basic", "quick", "small", "one-line"]
    if any(s in task_lower for s in complex_signals):
        complexity = "high"
    elif any(s in task_lower for s in simple_signals):
        complexity = "low"

    # Count action verbs (more verbs = more steps needed)
    action_verbs = ["write", "create", "build", "implement", "fix", "debug",
                    "test", "deploy", "configure", "setup", "optimize", "refactor"]
    action_count = sum(1 for v in action_verbs if v in task_lower)

    return {
        "language": language,
        "file_types": file_types,
        "complexity": complexity,
        "action_count": action_count,
        "task_lower": task_lower,
    }


def match_pattern(task: str, entities: dict) -> dict | None:
    """Find the best matching pattern for a task."""
    task_lower = entities["task_lower"]
    best_match = None
    best_score = 0

    for pattern in PATTERNS:
        score = 0
        matched_keywords = 0

        for kw in pattern["keywords"]:
            if kw in task_lower:
                score += 2
                matched_keywords += 1

        # Bonus for file type matches
        if "file_hints" in pattern:
            for ft in pattern["file_hints"]:
                if ft in task_lower or ft in entities["file_types"]:
                    score += 1

        # Require at least 1 keyword match
        if matched_keywords >= 1 and score > best_score:
            best_score = score
            best_match = pattern

    return best_match


def generate_steps(pattern: dict, entities: dict, task: str) -> list[DistilledStep]:
    """Generate steps from a matched pattern template."""
    steps = []
    template = pattern["template"]

    for i, (desc, step_type, agent) in enumerate(template):
        # Personalize description with detected entities
        personalized = desc
        if entities["language"] and i == 0:
            personalized = f"Analyze {entities['language']} requirements for: {task[:80]}"
        elif entities["language"] and "code" in step_type:
            personalized = f"{desc} ({entities['language']})"

        # Adjust for complexity
        if entities["complexity"] == "low" and len(template) > 3:
            # Skip verification for simple tasks
            if step_type == "verify" and i == len(template) - 1:
                continue

        steps.append(DistilledStep(
            description=personalized,
            step_type=step_type,
            agent=agent,
            confidence=min(0.9, 0.5 + (len(pattern["keywords"]) * 0.05)),
        ))

    return steps


# ── Public API ─────────────────────────────────────────────────

def plan_instantly(task: str, max_steps: int = 8) -> DistilledPlan | None:
    """Try to plan a task instantly without LLM.

    Returns DistilledPlan if pattern matched, None if LLM needed.
    """
    t0 = time.time()

    entities = extract_entities(task)
    pattern = match_pattern(task, entities)

    if pattern is None:
        return None

    steps = generate_steps(pattern, entities, task)

    # Trim to max steps
    if len(steps) > max_steps:
        steps = steps[:max_steps]

    elapsed = (time.time() - t0) * 1000

    logger.info(
        "Distilled plan: matched '%s' in %.1fms → %d steps",
        pattern["type"], elapsed, len(steps),
    )

    return DistilledPlan(
        steps=steps,
        matched_pattern=pattern["type"],
        planning_time_ms=elapsed,
        used_llm=False,
    )


def plan_with_fallback(task: str, max_steps: int = 8) -> DistilledPlan:
    """Plan with distilled fast-path, LLM fallback for novel tasks.

    This is the main entry point for the orchestrator.
    """
    # Try instant planning first
    plan = plan_instantly(task, max_steps)
    if plan is not None:
        return plan

    # Fall back to LLM planning (async, called from orchestrator)
    logger.info("No distilled pattern matched, LLM planning needed")
    return DistilledPlan(
        steps=[],
        matched_pattern=None,
        planning_time_ms=0,
        used_llm=True,
    )


# ── Convenience ────────────────────────────────────────────────

def get_pattern_coverage() -> dict[str, int]:
    """Show how many patterns we have for each task type."""
    coverage = {}
    for p in PATTERNS:
        coverage[p["type"]] = len(p["template"])
    return coverage
