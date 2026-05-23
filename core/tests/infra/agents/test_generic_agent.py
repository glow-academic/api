"""Tests for GenericAgent — construction, prompt building, model config."""

import pytest

from app.infra.agents.generic_agent import DEBUG_INFO_TOOL_SUFFIX, GenericAgent

pytestmark = pytest.mark.asyncio


def _make_agent(**overrides):
    """Helper to create a GenericAgent with sensible defaults."""
    defaults = {
        "agent_name": "test-agent",
        "system_prompt": "You are a test assistant.",
        "temperature": 0.5,
        "model_name": "gpt-4o",
        "provider": "openai",
        "api_key": "sk-test-key",
        "base_url": None,
        "reasoning": None,
    }
    defaults.update(overrides)
    return GenericAgent(**defaults)


async def test_get_system_prompt_appends_debug_suffix(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = _make_agent()
    prompt = agent.get_system_prompt()
    assert agent.system_prompt in prompt
    assert DEBUG_INFO_TOOL_SUFFIX in prompt


async def test_model_name_standard_provider(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = _make_agent(provider="openai", model_name="gpt-4o", base_url=None)
    assert agent.model == "gpt-4o"
    assert agent.custom_model is False
    assert agent.base_url is None


async def test_model_name_custom_provider(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = _make_agent(
        provider="custom", model_name="llama-3", base_url="http://localhost:8080"
    )
    assert agent.model == "custom/llama-3"
    assert agent.custom_model is True
    assert agent.base_url == "http://localhost:8080"


async def test_get_model_config_returns_expected_keys(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = _make_agent(temperature=0.9)
    config = agent.get_model_config()
    assert config["model"] == "gpt-4o"
    assert config["api_key"] == "sk-test-key"
    assert config["temperature"] == 0.9
    assert config["base_url"] is None


async def test_get_tool_functions_maps_by_name(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )

    def my_tool():
        return "ok"

    agent = _make_agent(tools=[my_tool])
    mapping = agent.get_tool_functions()
    assert "my_tool" in mapping
    assert mapping["my_tool"] is my_tool


async def test_decrypt_api_key_called_during_init(monkeypatch):
    called_with = []
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key",
        lambda k: (called_with.append(k), f"decrypted-{k}")[1],
    )
    agent = _make_agent(api_key="encrypted-key")
    assert called_with == ["encrypted-key"]
    assert agent.api_key == "decrypted-encrypted-key"


async def test_custom_model_detected_by_base_url(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = _make_agent(provider="openai", base_url="http://custom-endpoint.com")
    assert agent.custom_model is True
    assert agent.model == "openai/gpt-4o"
