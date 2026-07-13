from dash_prompts.templates import PromptTemplate


def test_prompt_template() -> None:
    prompt = PromptTemplate(name="greeting", template="Hello, {{name}}!")
    assert "{{name}}" in prompt.template
