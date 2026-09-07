"""Predictive Problem Detection (DASH Ultimate spec, Part 8).

Predicts problems before they break — resource trends, stale branches,
aging uncommitted work, dormant repos, stalled goals — each backed by
evidence and an honest likelihood. Never presents predictions as facts.
"""

from dash_backend.predictive.engine import PredictiveEngine, get_predictive_engine
from dash_backend.predictive.history import SampleStore
from dash_backend.predictive.predictors import Prediction

__all__ = ["Prediction", "PredictiveEngine", "SampleStore", "get_predictive_engine"]
