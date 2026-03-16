"""Base audio adapter interface for voice mode."""

from abc import ABC, abstractmethod
from typing import Any, Literal, Protocol

from pydantic import BaseModel

from app.infra.websocket.session_store import AudioSession


class AudioSessionConfig(BaseModel):
    """Configuration returned when initializing an audio session."""

    ephemeral_key: str | None = None  # For WebRTC client-side connections
    model: str
    voice: str | None = None
    instructions: str | None = None
    tools: list[dict[str, Any]] | None = None
    turn_detection: dict[str, Any] | None = None
    expires_in: int | None = None  # Seconds until ephemeral key expires


class AudioEventEmitter(Protocol):
    """Callback protocol for audio adapter events.

    Adapters call these methods instead of importing socket emit functions
    directly, keeping the infra layer decoupled from the socket layer.
    """

    # -- Assistant audio --

    async def on_audio_start(self, group_id: str) -> None:
        """Assistant started speaking (per-response audio begin)."""
        ...

    async def on_audio_delta(self, group_id: str, audio: bytes) -> None:
        """Assistant audio chunk (PCM16 bytes)."""
        ...

    async def on_audio_complete(self, group_id: str) -> None:
        """Assistant finished speaking (per-response audio done)."""
        ...

    # -- Assistant transcript (text alongside audio) --

    async def on_transcript_start(self, group_id: str, item_id: str) -> None:
        """Assistant transcript started (new output item)."""
        ...

    async def on_transcript_delta(self, group_id: str, transcript: str) -> None:
        """Assistant transcript chunk."""
        ...

    async def on_transcript_complete(
        self, group_id: str, item_id: str, transcript: str
    ) -> None:
        """Assistant transcript finalized (full text)."""
        ...

    # -- Tool calls --

    async def on_tool_call_start(
        self, group_id: str, item_id: str, call_id: str, name: str
    ) -> None:
        """Tool call started (function_call output item added)."""
        ...

    async def on_tool_call_delta(
        self, group_id: str, call_id: str, arguments_delta: str
    ) -> None:
        """Tool call arguments streaming chunk."""
        ...

    async def on_tool_call_complete(
        self, group_id: str, call_id: str, name: str, arguments: str
    ) -> None:
        """Tool call arguments finalized."""
        ...

    # -- User speech --

    async def on_user_speech_start(self, group_id: str, item_id: str) -> None:
        """VAD detected user started speaking."""
        ...

    async def on_user_speech_delta(
        self, group_id: str, item_id: str, transcript: str
    ) -> None:
        """User speech transcript chunk."""
        ...

    async def on_user_speech_complete(
        self,
        group_id: str,
        item_id: str,
        transcript: str,
        *,
        audio: bytes | None = None,
    ) -> None:
        """User speech finalized, optionally with buffered PCM16 audio."""
        ...

    # -- Lifecycle --

    async def on_error(self, group_id: str, error_message: str) -> None:
        """Adapter or provider error."""
        ...

    async def on_response_done(
        self, group_id: str, usage: dict[str, Any] | None
    ) -> None:
        """Provider response completed."""
        ...

    async def on_response_cancelled(
        self, group_id: str, usage: dict[str, Any] | None
    ) -> None:
        """Provider response cancelled (barge-in or explicit cancel)."""
        ...


class BaseAudioAdapter(ABC):
    """Base class for audio adapters.

    Audio adapters handle bidirectional audio streaming between clients and AI providers.
    Two implementation types are supported:

    - **WebRTC**: Client connects directly to provider (e.g., OpenAI Realtime API with ephemeral key)
    - **WebSocket**: Server maintains connection to provider, relays audio via Socket.IO

    For WebSocket adapters, the adapter consumes from session.inbound_queue and calls
    emitter callbacks for outbound audio events.
    """

    def __init__(self, emitter: AudioEventEmitter) -> None:
        self._emitter = emitter

    @abstractmethod
    def get_implementation_type(self) -> Literal["webrtc", "websocket"]:
        """Return the implementation type for this adapter.

        Returns:
            "webrtc" if client connects directly to provider
            "websocket" if server maintains the connection
        """
        pass

    @abstractmethod
    async def initialize_session(
        self,
        session: AudioSession,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
        voice: str | None = None,
        instructions: str | None = None,
        tools: list[dict[str, Any]] | None = None,
        **kwargs: Any,
    ) -> AudioSessionConfig:
        """Initialize an audio session.

        For WebRTC adapters, this generates an ephemeral key and returns config.
        For WebSocket adapters, this establishes the connection and starts loops.

        Args:
            session: The AudioSession containing queues and metadata
            api_key: Decrypted API key for the provider
            base_url: Provider's realtime WebSocket endpoint
            model: Model to use (e.g., "gpt-4o-realtime-preview")
            voice: Voice to use for TTS
            instructions: System instructions for the session
            tools: Tools available to the model
            **kwargs: Additional provider-specific options

        Returns:
            AudioSessionConfig with session details
        """
        pass

    @abstractmethod
    async def stop_session(self, session: AudioSession) -> None:
        """Stop an audio session and clean up resources.

        Args:
            session: The AudioSession to stop
        """
        pass
