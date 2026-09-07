"""Predictive problem detection (DASH 2.0 / Ultimate spec, Part 8).

OBSERVE -> IDENTIFY PATTERN -> PREDICT PROBLEM -> EXPLAIN EVIDENCE ->
SUGGEST ACTION -> OPTIONAL APPROVAL.

Honesty rules that this module enforces:
  * Predictions are never presented as guaranteed facts — every one carries
    `likelihood`, `evidence` (what DASH actually observed), and `confident`
    (whether enough history existed for a real projection).
  * A single reading never implies a trend. Trend predictors require a
    minimum number of samples spread over a minimum span, otherwise they say
    nothing rather than invent a slope.
  * Everything here is a pure function over plain data (device samples,
    branch listings, goal rows), so it is trivially testable and never
    touches the network or filesystem — the engine wires in live data.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# Trend credibility thresholds (hours). Under these, no trend is claimed.
_MIN_SPAN_HOURS = 6.0
_MIN_SAMPLES = 4

# When a projection reaches these thresholds it is worth surfacing.
_RAM_RISK_PCT = 92.0        # ram is risky once projected past this
_DISK_RISK_FREE_GB = 10.0   # disk is risky once projected below this
_STALE_BRANCH_DAYS = 30
_DORMANT_REPO_DAYS = 14
_DIRTY_RISK_HOURS = 12


@dataclass
class Prediction:
    """A forward-looking risk with the evidence behind it."""

    id: str
    category: str            # device | project | goals
    title: str
    message: str
    severity: str            # info | warning | high
    likelihood: float        # 0..1 — an honest estimate, never certainty
    action: str
    horizon: str = "unknown"  # human readable, e.g. "~9 days"
    confident: bool = False   # False => current-state read, not a projection
    evidence: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "message": self.message,
            "severity": self.severity,
            "likelihood": round(self.likelihood, 2),
            "action": self.action,
            "horizon": self.horizon,
            "confident": self.confident,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# Trend math (least-squares linear fit over time)
# ---------------------------------------------------------------------------

def _linear_fit(samples: List[Dict[str, Any]], key: str) -> Optional[Tuple[float, float]]:
    """Fit y = intercept + slope * hours_since_first. Returns (slope, intercept)
    or None when there is not enough usable data. Values are per hour."""
    pts: List[Tuple[float, float]] = []
    t0: Optional[float] = None
    for s in samples:
        ts = s.get("ts")
        val = s.get(key)
        if ts is None or val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(val):
            continue
        t0 = t0 if t0 is not None else float(ts)
        pts.append(((float(ts) - t0) / 3600.0, val))
    n = len(pts)
    if n < _MIN_SAMPLES:
        return None
    span = pts[-1][0] - pts[0][0]
    if span < _MIN_SPAN_HOURS:
        return None
    mean_x = sum(p[0] for p in pts) / n
    mean_y = sum(p[1] for p in pts) / n
    var_x = sum((p[0] - mean_x) ** 2 for p in pts)
    if var_x == 0:
        return None
    slope = sum((p[0] - mean_x) * (p[1] - mean_y) for p in pts) / var_x
    intercept = mean_y - slope * mean_x
    return slope, intercept


def _span_hours(samples: List[Dict[str, Any]]) -> float:
    ts = [float(s.get("ts") or 0) for s in samples if s.get("ts")]
    return (max(ts) - min(ts)) / 3600.0 if ts else 0.0


def _fmt_hours(hours: float) -> str:
    if hours <= 24:
        return f"~{max(1, int(round(hours)))} hour(s)"
    return f"~{max(1, int(round(hours / 24)))} day(s)"


# ---------------------------------------------------------------------------
# Device trend predictors
# ---------------------------------------------------------------------------

def predict_ram_exhaustion(samples: List[Dict[str, Any]]) -> Optional[Prediction]:
    """RAM climbing toward exhaustion. Requires a credible rising trend."""
    fit = _linear_fit(samples, "ram_pct")
    if fit is None:
        return None
    slope, _ = fit
    if slope <= 0.01:  # flat or falling: no exhaustion risk
        return None
    current = samples[-1].get("ram_pct")
    current = float(current) if current is not None else None
    if current is None or current <= 0:
        return None
    hours_to_risk = (float(_RAM_RISK_PCT) - current) / slope if slope > 0 else math.inf
    if hours_to_risk <= 0 or hours_to_risk > 24 * 7:
        return None  # already past the mark (reactive layer handles it) or too far out
    span = _span_hours(samples)
    confident = len(samples) >= _MIN_SAMPLES and span >= 24
    if hours_to_risk <= 24:
        likelihood, severity = 0.75, "high"
    elif hours_to_risk <= 72:
        likelihood, severity = 0.6, "warning"
    else:
        likelihood, severity = 0.45, "info"
    return Prediction(
        id="ram_trend_exhaustion",
        category="device",
        title="Memory usage is trending toward exhaustion",
        message=(
            f"RAM has risen from {samples[0].get('ram_pct')}% to {current:.0f}% "
            f"over the last {_fmt_hours(span)} and is projected to reach {_RAM_RISK_PCT:.0f}% "
            f"in {_fmt_hours(hours_to_risk)} at the current rate."
        ),
        severity=severity,
        likelihood=likelihood,
        action="Check the top memory consumers (see context snapshot) or close idle applications.",
        horizon=_fmt_hours(hours_to_risk),
        confident=confident,
        evidence=[
            f"{len(samples)} samples over {_fmt_hours(span)}",
            f"rising {samples[0].get('ram_pct')}% -> {current:.0f}%",
        ],
    )


def predict_disk_fill(samples: List[Dict[str, Any]]) -> Optional[Prediction]:
    """Disk filling toward < free threshold. Requires a credible falling trend."""
    fit = _linear_fit(samples, "disk_free_gb")
    if fit is None:
        return None
    slope, _ = fit
    if slope >= -0.0005:  # not shrinking meaningfully
        return None
    current_free = samples[-1].get("disk_free_gb")
    current_free = float(current_free) if current_free is not None else None
    if current_free is None:
        return None
    if current_free <= _DISK_RISK_FREE_GB:
        return None  # already low right now; reactive layer handles it
    hours_to_risk = (float(_DISK_RISK_FREE_GB) - current_free) / slope  # slope negative -> positive
    if hours_to_risk <= 0 or hours_to_risk > 24 * 90:
        return None
    span = _span_hours(samples)
    confident = len(samples) >= _MIN_SAMPLES and span >= 24
    days = hours_to_risk / 24.0
    if days <= 14:
        likelihood, severity = 0.65, "warning"
    else:
        likelihood, severity = 0.5, "info"
    return Prediction(
        id="disk_fill_projection",
        category="device",
        title="Disk space is shrinking toward low-free",
        message=(
            f"Free disk has fallen from {samples[0].get('disk_free_gb')} GB to {current_free:.1f} GB "
            f"over the last {_fmt_hours(span)} and is projected below {_DISK_RISK_FREE_GB:.0f} GB "
            f"in {_fmt_hours(hours_to_risk)} at the current rate."
        ),
        severity=severity,
        likelihood=likelihood,
        action="Review large files or build artifacts; consider cleanup before it becomes urgent.",
        horizon=_fmt_hours(hours_to_risk),
        confident=confident,
        evidence=[
            f"{len(samples)} samples over {_fmt_hours(span)}",
            f"falling {samples[0].get('disk_free_gb')} GB -> {current_free:.1f} GB free",
        ],
    )


# ---------------------------------------------------------------------------
# Project predictors
# ---------------------------------------------------------------------------

def predict_stale_branches(project: Dict[str, Any], branch_info: Optional[List[Tuple[str, str]]] = None) -> Optional[Prediction]:
    """Local branches with no commit in N days (current branch excluded).

    `branch_info` is [(name, 'YYYY-MM-DD')]; when omitted it is derived from
    git (engine supplies live data; tests inject fabricated listings).
    """
    if not project:
        return None
    current = project.get("branch")
    if branch_info is None:
        branch_info = _git_branch_info(project.get("repo_root"))
    if not branch_info:
        return None
    cutoff = datetime.now()
    stale: List[Tuple[str, str, int]] = []
    for name, date_str in branch_info:
        if name == current or name in ("HEAD",):
            continue
        try:
            d = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        except (TypeError, ValueError):
            continue
        days = (cutoff - d).days
        if days >= _STALE_BRANCH_DAYS:
            stale.append((name, date_str, days))
    if not stale:
        return None
    stale.sort(key=lambda x: x[2], reverse=True)
    names = ", ".join(f"{n} ({d}d)" for n, _, d in stale[:4])
    repo = project.get("repo_name", "project")
    return Prediction(
        id="stale_branches",
        category="project",
        title=f"{len(stale)} stale branch(es) in {repo}",
        message=(
            f"{len(stale)} local branch(es) in {repo} have had no commit for {_STALE_BRANCH_DAYS}+ days: "
            f"{names}{' +%d more' % (len(stale) - 4) if len(stale) > 4 else ''}. "
            "Stale branches drift from main and get harder to merge."
        ),
        severity="info",
        likelihood=0.6,
        action="Review and delete or archive the stale branches (git branch -d / git merge).",
        confident=True,
        evidence=[f"{name}: last commit {date}" for name, date, _ in stale[:5]],
    )


def _git_branch_info(repo_root: Optional[str]) -> List[Tuple[str, str]]:
    if not repo_root:
        return []
    from pathlib import Path

    from dash_backend.context.collectors import _git

    out = _git(
        Path(repo_root),
        "for-each-ref",
        "--format=%(refname:short)|%(committerdate:short)",
        "refs/heads",
    )
    if not out:
        return []
    rows: List[Tuple[str, str]] = []
    for line in out.splitlines():
        if "|" in line:
            name, date_str = line.rsplit("|", 1)
            rows.append((name.strip(), date_str.strip()))
    return rows


def predict_repo_dormancy(project: Dict[str, Any]) -> Optional[Prediction]:
    """The pinned/active repo has been silent for a long time."""
    last = (project or {}).get("last_commit")
    if not last:
        return None
    try:
        date_part = last.rsplit("|", 1)[-1].strip()
        d = datetime.strptime(date_part, "%Y-%m-%d")
    except Exception:
        return None
    days = (datetime.now() - d).days
    if days < _DORMANT_REPO_DAYS:
        return None
    if (project.get("changed_files") or 0) > 0:
        return None  # not dormant if there is uncommitted work
    repo = project.get("repo_name", "project")
    return Prediction(
        id="repo_dormant",
        category="project",
        title=f"{repo} has been dormant for {days} days",
        message=(
            f"No commit on {repo} since {d.date()} ({days} days). "
            "Long gaps can mean stalled work or an abandoned effort."
        ),
        severity="info",
        likelihood=0.5,
        action="Check whether this effort stalled; continue, wrap it up, or archive it.",
        horizon=f"{days} days",
        confident=True,
        evidence=[f"last commit {last}", f"{days} days without activity"],
    )


def predict_dirty_aging(
    repo: Dict[str, Any],
    prev_observation: Optional[Dict[str, Any]],
    now: Optional[float] = None,
) -> Optional[Prediction]:
    """Uncommitted work that has been outstanding for hours across polls."""
    changed = repo.get("changed_files") or 0
    if changed <= 0:
        return None
    if not prev_observation:
        return None  # first time we have seen this state
    since = prev_observation.get("dirty_since") or prev_observation.get("seen_at")
    if not since:
        return None
    now = now or time.time()
    hours = (now - since) / 3600.0
    if hours < _DIRTY_RISK_HOURS:
        return None
    name = repo.get("repo_name", "project")
    branch = repo.get("branch", "?")
    return Prediction(
        id="dirty_work_aging",
        category="project",
        title=f"Uncommitted work in {name} has been open for {_fmt_hours(hours)}",
        message=(
            f"{changed} modified file(s) on branch {branch} have been uncommitted "
            f"since the last observation. Uncommitted work is at risk of being lost "
            "or forgotten."
        ),
        severity="warning",
        likelihood=0.6,
        action="Commit the changes (or stash them) so the work is safe.",
        horizon=_fmt_hours(hours),
        confident=True,
        evidence=[f"{changed} modified file(s)", f"first seen dirty {_fmt_hours(hours)} ago"],
    )


# ---------------------------------------------------------------------------
# Goal predictors
# ---------------------------------------------------------------------------

def predict_stalled_goals(rows: List[Dict[str, Any]]) -> Optional[Prediction]:
    """Goals stuck in pending/running for a long time (no deadline field exists
    yet, so "stalled" = created long ago and never finished)."""
    if not rows:
        return None
    oldest = min(rows, key=lambda r: r.get("created_at") or "")
    names = ", ".join(r.get("name", "?") for r in rows[:4])
    extra = f" (+{len(rows) - 4} more)" if len(rows) > 4 else ""
    return Prediction(
        id="goals_stalled",
        category="goals",
        title=f"{len(rows)} goal(s) have been open for 3+ days",
        message=(
            f"{names}{extra} {'were' if len(rows) > 1 else 'was'} created "
            f"{oldest.get('created_at', '?')[:10]} and {'are' if len(rows) > 1 else 'is'} "
            "still pending/running with no completion."
        ),
        severity="info",
        likelihood=0.5,
        action="Review these goals: continue them, break them down, or cancel them.",
        confident=True,
        evidence=[f"{r.get('name', '?')} [{r.get('status')}] created {str(r.get('created_at'))[:10]}" for r in rows[:5]],
    )
