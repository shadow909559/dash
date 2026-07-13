"""AI core package tests."""

from dash_ai_core import __version__
from dash_ai_core.types import AIProvider


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_ai_provider_enum() -> None:
    assert AIProvider.OPENAI.value == "openai"
    assert AIProvider.OLLAMA.value == "ollama"
