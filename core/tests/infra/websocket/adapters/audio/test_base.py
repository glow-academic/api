"""Tests for audio adapter base — AudioSessionConfig, AudioEventEmitter, BaseAudioAdapter."""

from __future__ import annotations

from typing import Any, Literal
from unittest.mock import AsyncMock

import pytest

from app.infra.websocket.adapters.audio.base import (
    AudioEventEmitter,
    AudioSessionConfig,
    BaseAudioAdapter,
)
from app.infra.websocket.session_store import AudioSession

pytestmark = pytest.mark.asyncio


async def test_audio_session_config_defaults():
    """AudioSessionConfig has correct default values."""
    config = AudioSessionConfig(model="gpt-4o-realtime")

    assert config.model == "gpt-4o-realtime"
    assert config.ephemeral_key is None
    assert config.voice is None
    assert config.instructions is None
    assert config.tools is None
    assert config.turn_detection is None
    assert config.expires_in is None


async def test_audio_session_config_with_all_fields():
    """AudioSessionConfig accepts all fields."""
    config = AudioSessionConfig(
        ephemeral_key="ek-123",
        model="gpt-4o-realtime-preview",
        voice="alloy",
        instructions="Be helpful",
        tools=[{"type": "function", "name": "search"}],
        turn_detection={"type": "server_vad"},
        expires_in=3600,
    )

    assert config.ephemeral_key == "ek-123"
    assert config.voice == "alloy"
    assert config.instructions == "Be helpful"
    assert len(config.tools) == 1
    assert config.expires_in == 3600


async def test_base_audio_adapter_is_abstract():
    """BaseAudioAdapter cannot be instantiated — has abstract methods."""
    emitter = AsyncMock(spec=AudioEventEmitter)

    with pytest.raises(TypeError):
        BaseAudioAdapter(emitter)


async def test_concrete_audio_adapter_can_be_instantiated():
    """A concrete subclass implementing all abstract methods works."""

    class TestAdapter(BaseAudioAdapter):
        def get_implementation_type(self) -> Literal["webrtc", "websocket"]:
            return "websocket"

        async def initialize_session(
            self,
            session: AudioSession,
            api_key: str,
            **kwargs: Any,
        ) -> AudioSessionConfig:
            return AudioSessionConfig(model="test-model", voice="echo")

        async def stop_session(self, session: AudioSession) -> None:
            pass

    emitter = AsyncMock()
    adapter = TestAdapter(emitter)

    assert adapter.get_implementation_type() == "websocket"
    assert adapter._emitter is emitter


async def test_audio_session_config_serialization():
    """AudioSessionConfig serializes to dict."""
    config = AudioSessionConfig(
        model="gpt-4o",
        voice="shimmer",
        instructions="test",
    )
    data = config.model_dump()

    assert data["model"] == "gpt-4o"
    assert data["voice"] == "shimmer"
    assert data["ephemeral_key"] is None
