"""Tests for run_agent_with_tools — agent execution loop with mocked litellm."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.infra.agents.run_agent import AgentRunResult, MockContextWrapper, run_agent_with_tools

pytestmark = pytest.mark.asyncio


@dataclass
class _FakeUsage:
    prompt_tokens: int = 10
    completion_tokens: int = 5
    total_tokens: int = 15


@dataclass
class _FakeMessage:
    content: str | None = "Hello from AI"
    tool_calls: list | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage | None = None


@dataclass
class _FakeResponse:
    choices: list | None = None
    usage: _FakeUsage | None = None


async def test_run_agent_returns_text_when_no_tool_calls(monkeypatch):
    response = _FakeResponse(
        choices=[_FakeChoice(message=_FakeMessage(content="Final answer"))],
        usage=_FakeUsage(),
    )
    mock_completion = AsyncMock(return_value=response)
    monkeypatch.setattr("app.infra.agents.run_agent.litellm.acompletion", mock_completion)

    result = await run_agent_with_tools(
        messages=[{"role": "user", "content": "Hi"}],
        model="gpt-4",
        system_prompt="You are helpful.",
    )

    assert isinstance(result, AgentRunResult)
    assert result.final_output == "Final answer"
    assert result.usage["total_tokens"] == 15
    mock_completion.assert_called_once()


async def test_run_agent_passes_system_prompt_as_first_message(monkeypatch):
    captured_kwargs: dict[str, Any] = {}

    async def capture_completion(**kwargs):
        captured_kwargs.update(kwargs)
        return _FakeResponse(
            choices=[_FakeChoice(message=_FakeMessage(content="ok"))],
            usage=_FakeUsage(),
        )

    monkeypatch.setattr("app.infra.agents.run_agent.litellm.acompletion", capture_completion)

    await run_agent_with_tools(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4",
        system_prompt="Be a pirate.",
    )

    msgs = captured_kwargs["messages"]
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == "Be a pirate."
    assert msgs[1]["role"] == "user"


async def test_run_agent_handles_empty_choices(monkeypatch):
    response = _FakeResponse(choices=[], usage=_FakeUsage())
    monkeypatch.setattr(
        "app.infra.agents.run_agent.litellm.acompletion",
        AsyncMock(return_value=response),
    )

    result = await run_agent_with_tools(
        messages=[{"role": "user", "content": "Hi"}],
        model="gpt-4",
    )

    assert result.final_output == ""


async def test_mock_context_wrapper_has_usage():
    usage = {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3}
    wrapper = MockContextWrapper(usage=usage)
    assert wrapper.usage == usage


async def test_run_agent_accumulates_usage_across_iterations(monkeypatch):
    """When the model makes a tool call then a final text response, usage is summed."""
    import json

    @dataclass
    class _FakeFunction:
        name: str = "test_tool"
        arguments: str = "{}"

    @dataclass
    class _FakeToolCall:
        id: str = "tc_1"
        type: str = "function"
        function: Any = None

    call_count = 0

    async def multi_turn_completion(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # First call: model wants to use a tool
            tc = _FakeToolCall(function=_FakeFunction())
            msg = _FakeMessage(content=None, tool_calls=[tc])
            return _FakeResponse(
                choices=[_FakeChoice(message=msg)],
                usage=_FakeUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            )
        else:
            # Second call: model returns final text
            return _FakeResponse(
                choices=[_FakeChoice(message=_FakeMessage(content="Done"))],
                usage=_FakeUsage(prompt_tokens=20, completion_tokens=10, total_tokens=30),
            )

    monkeypatch.setattr("app.infra.agents.run_agent.litellm.acompletion", multi_turn_completion)

    result = await run_agent_with_tools(
        messages=[{"role": "user", "content": "test"}],
        model="gpt-4",
        tool_functions={"test_tool": lambda: "tool result"},
    )

    assert result.final_output == "Done"
    assert result.usage["prompt_tokens"] == 30
    assert result.usage["completion_tokens"] == 15
    assert result.usage["total_tokens"] == 45
