"""Tests for build_voice_agent — voice agent factory with persona tools."""

import pytest

from app.infra.agents.generic_agent import DEBUG_INFO_TOOL_SUFFIX, GenericAgent
from app.infra.agents.utils.build_voice_agent import build_voice_agent

pytestmark = pytest.mark.asyncio


def _make_context(**overrides):
    defaults = {
        "model_name": "gpt-4o",
        "provider_name": "openai",
        "base_url": None,
        "api_key": "sk-test",
        "temperature": 0.7,
        "reasoning": None,
    }
    defaults.update(overrides)
    return defaults


async def test_build_voice_agent_returns_agent_and_instructions(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent, instructions = build_voice_agent(
        context=_make_context(),
        persona_tools=[],
        base_system_prompt="You manage a conversation.",
        persona_instructions_map={"Doctor": "Be empathetic."},
    )
    assert isinstance(agent, GenericAgent)
    assert isinstance(instructions, str)


async def test_voice_agent_instructions_contain_persona_names(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    personas = {"Alice": "Friendly nurse.", "Bob": "Grumpy patient."}
    _, instructions = build_voice_agent(
        context=_make_context(),
        persona_tools=[],
        base_system_prompt="Prompt",
        persona_instructions_map=personas,
    )
    assert "Alice" in instructions
    assert "Bob" in instructions
    assert "Friendly nurse." in instructions
    assert "Grumpy patient." in instructions


async def test_voice_agent_instructions_include_tool_usage(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    _, instructions = build_voice_agent(
        context=_make_context(),
        persona_tools=[],
        base_system_prompt="Base",
        persona_instructions_map={"Nurse": "Be kind."},
    )
    assert "speak" in instructions.lower()
    assert DEBUG_INFO_TOOL_SUFFIX in instructions


async def test_voice_agent_disables_parallel_tool_calls(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent, _ = build_voice_agent(
        context=_make_context(),
        persona_tools=[],
        base_system_prompt="Base",
        persona_instructions_map={"Doc": ""},
    )
    assert agent.parallel_tool_calls is False


async def test_voice_agent_name_is_voice_agent(monkeypatch):
    monkeypatch.setattr(
        "app.infra.agents.generic_agent.decrypt_api_key", lambda k: k
    )
    agent, _ = build_voice_agent(
        context=_make_context(),
        persona_tools=[],
        base_system_prompt="Base",
        persona_instructions_map={"Doc": ""},
    )
    assert agent.agent_name == "Voice Agent"
