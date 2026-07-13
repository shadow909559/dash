from dash_agents.base import AgentConfig


def test_agent_config() -> None:
    config = AgentConfig(name="assistant")
    assert config.name == "assistant"
