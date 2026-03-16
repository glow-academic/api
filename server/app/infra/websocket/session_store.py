"""Session store for audio generation - tracks queues and WebSocket connections.

Sessions are keyed by chat_id (primary, client-facing), run_id (internal),
and group_id (internal). The sid is stored for emitting back to the client.
"""

import asyncio
import time
from typing import Any

_session_store: dict[str, "AudioSession"] = {}


class AudioSession:
    """Audio session data structure.

    Primary key: chat_id (client-facing, one active session per chat).
    Secondary keys: run_id, group_id (internal lookups).
    """

    def __init__(
        self,
        sid: str,
        chat_id: str,
        run_id: str,
        group_id: str,
        conversation_id: str | None = None,
        artifact_type: str | None = None,
        resource_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.sid = sid
        self.chat_id = chat_id
        self.run_id = run_id
        self.group_id = group_id
        self.conversation_id = conversation_id
        # Generation context — set at session creation so the emitter can
        # build canonical generate_text_*/generate_call_* payloads without extra lookups.
        self.artifact_type = artifact_type
        self.resource_type = resource_type
        self.metadata = metadata or {}
        # Tool call context — schemas for resolving output fields, state for
        # accumulating streaming arguments (same logic as generate_artifact.py).
        self.tool_output_schemas: dict[str, dict[str, str]] = {}
        self.tool_call_states: dict[str, dict[str, Any]] = {}
        self.inbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self.outbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.last_activity: float = time.monotonic()
        self.muted = False
        # User speech audio buffering — accumulates PCM16 frames between
        # VAD speech_started and speech_stopped for saving to disk.
        self.speech_buffering = False
        self.speech_audio_buffer = bytearray()
        self.oa_ws_connection: Any | None = None  # OpenAI WebSocket connection
        self.item_id_to_upload_id: dict[str, str] = {}
        self.response_id_to_upload_id: dict[str, str] = {}


def create_session(
    sid: str,
    chat_id: str,
    run_id: str,
    group_id: str,
    conversation_id: str | None = None,
    artifact_type: str | None = None,
    resource_type: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AudioSession:
    """Create a new audio session, keyed by chat_id, run_id, and group_id."""
    session = AudioSession(
        sid,
        chat_id,
        run_id,
        group_id,
        conversation_id,
        artifact_type=artifact_type,
        resource_type=resource_type,
        metadata=metadata,
    )
    _session_store[chat_id] = session
    _session_store[run_id] = session
    _session_store[group_id] = session
    return session


def remove_session(session_key: str) -> None:
    """Remove session by any key (chat_id, run_id, or group_id)."""
    session = _session_store.get(session_key)
    if session:
        _session_store.pop(session.chat_id, None)
        _session_store.pop(session.run_id, None)
        _session_store.pop(session.group_id, None)


def get_session_by_chat_id(chat_id: str) -> AudioSession | None:
    """Get session by chat ID (client-facing lookup)."""
    return _session_store.get(chat_id)


def get_session_by_run_id(run_id: str) -> AudioSession | None:
    """Get session by run ID."""
    return _session_store.get(run_id)


def get_session_by_group_id(group_id: str) -> AudioSession | None:
    """Get session by group ID (internal lookup)."""
    return _session_store.get(group_id)


def rotate_run_id(session: AudioSession, new_run_id: str) -> None:
    """Rotate the run_id on an existing session (audio continuation).

    Removes the old run_id key and adds the new one, keeping chat_id
    and group_id keys intact.
    """
    _session_store.pop(session.run_id, None)
    session.run_id = new_run_id
    _session_store[new_run_id] = session


def get_session_by_sid(sid: str) -> AudioSession | None:
    """Get session by socket ID (disconnect cleanup only)."""
    for session in set(_session_store.values()):
        if session.sid == sid:
            return session
    return None


def get_stale_sessions(timeout: float = 300.0) -> list[AudioSession]:
    """Return sessions inactive for longer than timeout seconds (default 5 min)."""
    now = time.monotonic()
    seen: set[str] = set()
    stale: list[AudioSession] = []
    for session in _session_store.values():
        if session.chat_id not in seen:
            seen.add(session.chat_id)
            if (now - session.last_activity) > timeout:
                stale.append(session)
    return stale
