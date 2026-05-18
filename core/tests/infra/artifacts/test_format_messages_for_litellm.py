"""Tests for format_messages_for_litellm."""
import pytest
from app.infra.artifacts.format_messages_for_litellm import format_messages_for_litellm
pytestmark = pytest.mark.asyncio

async def test_empty_input():
    result = format_messages_for_litellm([])
    assert result == []

async def test_simple_user_message():
    items = [{"role": "user", "content": "Hello"}]
    result = format_messages_for_litellm(items)
    assert len(result) == 1
    assert result[0]["role"] == "user"
    assert result[0]["content"] == "Hello"

async def test_multiple_messages():
    items = [
        {"role": "user", "content": "Hi"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "How are you?"},
    ]
    result = format_messages_for_litellm(items)
    assert len(result) == 3
    assert result[1]["role"] == "assistant"

async def test_audio_file_message():
    items = [{"role": "user", "content": "Audio file to process: /path/to/audio.wav"}]
    result = format_messages_for_litellm(items)
    assert len(result) == 1
    assert "Audio file to process" in result[0]["content"]
