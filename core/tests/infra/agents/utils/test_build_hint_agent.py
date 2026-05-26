"""Tests for build_hint_agent — hint agent factory."""

import pytest

from app.infra.agents.generic_agent import GenericAgent
from app.infra.agents.utils.build_hint_agent import build_hint_agent

pytestmark = pytest.mark.asyncio


def _make_context(**overrides):
    defaults = {
        "agent_name": "hint-agent",
        "system_prompt": "Generate a hint for the student.",
        "temperature": 0.7,
        "model_name": "gpt-4o",
        "provider": "openai",
        "base_url": None,
        "api_key": "sk-test",
        "reasoning": None,
    }
    defaults.update(overrides)
    return defaults


async def test_build_hint_agent_returns_generic_agent(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = build_hint_agent(_make_context(), hint_tools=[])
    assert isinstance(agent, GenericAgent)
    assert agent.agent_name == "hint-agent"


async def test_build_hint_agent_uses_context_values(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    ctx = _make_context(temperature=0.3, model_name="gpt-3.5-turbo")
    agent = build_hint_agent(ctx, hint_tools=[])
    assert agent.temperature == 0.3
    assert agent.model_name == "gpt-3.5-turbo"
    assert agent.system_prompt == "Generate a hint for the student."


async def test_build_hint_agent_passes_tools(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )

    def fake_tool():
        pass

    agent = build_hint_agent(_make_context(), hint_tools=[fake_tool])
    assert len(agent.tools) == 1
    assert agent.tools[0] is fake_tool


async def test_build_hint_agent_enables_parallel_tool_calls(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent = build_hint_agent(_make_context(), hint_tools=[])
    assert agent.parallel_tool_calls is True
