"""Tests for build_tool_from_config — dynamic tool function generation."""

import asyncio

import pytest

from app.infra.tools.build_tool_from_config import (
    _generate_return_message,
    build_tool_from_config,
)

pytestmark = pytest.mark.asyncio


# -- build_tool_from_config happy path -----------------------------------------


async def test_builds_callable_async_function():
    """build_tool_from_config returns an async callable with the correct name."""
    config = {
        "name": "create_summary",
        "description": "Create a summary of the content.",
        "arguments": {"text": {"type": "string", "required": True}},
        "argument_descriptions": {"text": "The text to summarize"},
        "argument_defaults": {},
    }

    tool = build_tool_from_config(config)

    assert callable(tool)
    assert asyncio.iscoroutinefunction(tool)
    assert tool.__name__ == "create_summary"


async def test_built_function_returns_success_message():
    """The generated function returns the expected success message string."""
    config = {
        "name": "create_summary",
        "description": "Create a summary of the content.",
        "arguments": {"text": {"type": "string", "required": True}},
        "argument_descriptions": {"text": "The text to summarize"},
        "argument_defaults": {},
    }

    tool = build_tool_from_config(config)
    result = await tool(text="Hello world")

    assert result == "Created summary successfully"


async def test_built_function_has_docstring():
    """The generated function has the tool description as its docstring."""
    config = {
        "name": "create_note",
        "description": "Create a new note for this session.",
        "arguments": {"content": {"type": "string", "required": True}},
        "argument_descriptions": {"content": "Note content"},
        "argument_defaults": {},
    }

    tool = build_tool_from_config(config)

    assert tool.__doc__ == "Create a new note for this session."


async def test_built_function_accepts_optional_params():
    """Optional parameters can be passed or omitted."""
    config = {
        "name": "set_rating",
        "description": "Set a rating for the item.",
        "arguments": {
            "score": {"type": "integer", "required": True},
            "comment": {"type": "string", "required": False},
        },
        "argument_descriptions": {
            "score": "Rating score",
            "comment": "Optional comment",
        },
        "argument_defaults": {"comment": None},
    }

    tool = build_tool_from_config(config)
    result = await tool(score=5, comment="Great")

    assert result == "Set rating successfully"


# -- error cases ---------------------------------------------------------------


async def test_raises_when_name_missing():
    """build_tool_from_config raises ValueError when name is empty."""
    config = {
        "name": "",
        "description": "No name tool",
        "arguments": {},
        "argument_descriptions": {},
        "argument_defaults": {},
    }

    with pytest.raises(ValueError, match="must have a 'name' field"):
        build_tool_from_config(config)


async def test_default_description_when_empty():
    """When description is empty, a default is used."""
    config = {
        "name": "my_tool",
        "description": "",
        "arguments": {},
        "argument_descriptions": {},
        "argument_defaults": {},
    }

    tool = build_tool_from_config(config)
    # Should not raise — default description is applied
    assert tool.__doc__ == "Tool my_tool"


# -- _generate_return_message --------------------------------------------------


async def test_generate_return_message_create_prefix():
    assert _generate_return_message("create_title", "Create a title") == "Created title successfully"


async def test_generate_return_message_generate_prefix():
    assert _generate_return_message("generate_html", "Generate HTML") == "Generated html successfully"


async def test_generate_return_message_set_prefix():
    assert _generate_return_message("set_status", "Set the status") == "Set status successfully"


async def test_generate_return_message_fallback():
    """Unknown prefix extracts verb + noun from description."""
    result = _generate_return_message("analyze_data", "Analyze the data carefully")
    assert "successfully" in result
