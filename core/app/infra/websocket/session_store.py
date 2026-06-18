"""Session store for audio generation - tracks queues and WebSocket connections.

Sessions are keyed by chat_id (primary, client-facing), run_id (internal),
and group_id (internal). The sid is stored for emitting back to the client.
"""

import asyncio
import time
from typing import Any

_session_store: dict[str, "AudioSession"] = {}

# ── Boundedness caps (report-22 VOICE2/VOICE3) ───────────────────────────────
# A single realtime PCM frame is small (PCM16@24kHz, ~100ms ≈ 4.8 KB); anything
# over this is malformed/abusive and is rejected rather than buffered.
MAX_FRAME_BYTES = 1_000_000  # 1 MB — generous per-frame ceiling
# Soft-staging buffer (``pending_frames``) total cap. The live inbound_queue is
# capped at 500 frames; the soft path (POST /chat/speak soft=True) had NO
# backpressure, so a session owner could append unbounded PCM that's only freed
# on an ack that may never come → single-session OOM. Bound the total bytes.
PENDING_FRAMES_MAX_BYTES = 16_000_000  # 16 MB across all pending idempotency keys
# Accumulated inbound speech between VAD speech_started/stopped. When the
# provider VAD never fires speech_stopped (turn_detection omitted by default)
# this grew without bound; cap it (~11 min of 24kHz PCM16).
SPEECH_BUFFER_MAX_BYTES = 32_000_000  # 32 MB
# Hard max wall-clock lifetime of a single voice session (report-22 VOICE1
# follow-up). The idle reaper only fires when ``last_activity`` goes stale, but
# ``touch()`` now bumps on EVERY provider event — so a wedged provider (endless
# keep-alives, a spinning tool-loop) keeps the session perpetually "fresh" and
# the idle check can never reap it. This absolute ceiling, measured from
# session creation and immune to ``touch()``, guarantees even a busy-but-wedged
# session is force-reaped. Generous so it never clips a legitimate call.
MAX_SESSION_LIFETIME = 3600.0  # 1 hour


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
        session_id: str | None = None,
        profile_id: str | None = None,
        artifact_type: str | None = None,
        resource_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.sid = sid
        self.chat_id = chat_id
        self.run_id = run_id
        self.group_id = group_id
        self.conversation_id = conversation_id
        self.session_id = session_id
        self.profile_id = profile_id
        # Generation context — set at session creation so the emitter can
        # build canonical generate_text_*/generate_call_* payloads without extra lookups.
        self.artifact_type = artifact_type
        self.resource_type = resource_type
        self.metadata = metadata or {}
        # Tool call context — schemas for resolving output fields, state for
        # accumulating streaming arguments (same logic as execute.py).
        self.tool_output_schemas: dict[str, dict[str, str]] = {}
        self.tool_call_states: dict[str, dict[str, Any]] = {}
        # Full tool definitions keyed by sanitized name. The realtime
        # downlink loop uses this to look up a tool when the provider
        # emits ``response.function_call_arguments.done`` so it can
        # execute the tool via ``execute_infra_operation`` and feed the
        # result back as ``conversation.item.create {function_call_output}``.
        self.tool_def_by_name: dict[str, dict[str, Any]] = {}
        self.inbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=500)
        self.outbound_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        # Soft/accept staging buffer for /attempt/chat/speak — frames pushed
        # with soft=True are held here (keyed by idempotency_key) and flushed
        # into ``inbound_queue`` on accept (mirrors refresh's "record intent,
        # don't enqueue until ack" — in-memory since the queue itself is).
        self.pending_frames: dict[str, list[bytes]] = {}
        self.last_activity: float = time.monotonic()
        # Wall-clock creation time — the anchor for the hard max-lifetime
        # backstop in ``get_stale_sessions``. Unlike ``last_activity`` this is
        # NEVER refreshed by ``touch()``, so it catches a wedged-but-busy session
        # that the idle check alone would never reap (report-22 VOICE1 follow-up).
        self.created_at: float = time.monotonic()
        # VOICE4-b: the first turn of a voice session is metered by
        # /attempt/generate; the first run-complete must NOT meter again (else an
        # N-turn call costs N+1). Flipped true on the first run-complete; only
        # continuations (turn 2+) are metered. See run_complete_impl.
        self.first_audio_turn_complete_seen: bool = False
        self.muted = False
        # User speech audio buffering — accumulates PCM16 frames between
        # VAD speech_started and speech_stopped for disk persistence.
        self.speech_buffering = False
        self.speech_audio_buffer = bytearray()
        self.oa_ws_connection: Any | None = None  # OpenAI WebSocket connection
        self.item_id_to_upload_id: dict[str, str] = {}
        self.response_id_to_upload_id: dict[str, str] = {}
        # Accumulated assistant PCM16 deltas for the current turn, flushed
        # to disk via audio_upload_attempt_impl on response.audio.done.
        self.assistant_audio_buffer = bytearray()
        # Running byte total of ``pending_frames`` for the O(1) VOICE2 cap check.
        self.pending_frames_bytes: int = 0

    def touch(self) -> None:
        """Refresh the liveness timestamp (VOICE1).

        Call on ANY activity — inbound client frames, OUTBOUND assistant frames
        sent to the client, and provider events — not just inbound. The reaper
        (``get_stale_sessions``) closes sessions idle past the window; bumping
        only on inbound meant a long assistant monologue, a slow tool-loop, or a
        user who is merely LISTENING for > the window got reaped mid-turn with
        the provider connection torn down under them.
        """
        self.last_activity = time.monotonic()

    def stage_pending_frame(self, key: str, frame: bytes) -> bool:
        """Append a soft-staged frame under ``key``, enforcing the total-bytes
        cap (VOICE2). Returns ``False`` (caller must reject) if the frame is
        oversized or staging it would exceed ``PENDING_FRAMES_MAX_BYTES``."""
        if len(frame) > MAX_FRAME_BYTES:
            return False
        if self.pending_frames_bytes + len(frame) > PENDING_FRAMES_MAX_BYTES:
            return False
        self.pending_frames.setdefault(key, []).append(frame)
        self.pending_frames_bytes += len(frame)
        return True

    def pop_pending_frames(self, key: str) -> list[bytes]:
        """Pop a staged key's frames and decrement the running byte total."""
        frames = self.pending_frames.pop(key, [])
        self.pending_frames_bytes -= sum(len(f) for f in frames)
        if self.pending_frames_bytes < 0:  # defensive; should never happen
            self.pending_frames_bytes = 0
        return frames

    def buffer_speech_audio(self, frame: bytes) -> bool:
        """Append inbound speech PCM, enforcing the per-frame and total-buffer
        caps (VOICE3). Returns ``False`` (caller drops the frame) if the frame
        is oversized or the buffer is already at ``SPEECH_BUFFER_MAX_BYTES``."""
        if len(frame) > MAX_FRAME_BYTES:
            return False
        if len(self.speech_audio_buffer) + len(frame) > SPEECH_BUFFER_MAX_BYTES:
            return False
        self.speech_audio_buffer.extend(frame)
        return True


def create_session(
    sid: str,
    chat_id: str,
    run_id: str,
    group_id: str,
    conversation_id: str | None = None,
    session_id: str | None = None,
    profile_id: str | None = None,
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
        session_id=session_id,
        profile_id=profile_id,
        artifact_type=artifact_type,
        resource_type=resource_type,
        metadata=metadata,
    )
    _session_store[chat_id] = session
    _session_store[run_id] = session
    _session_store[group_id] = session
    if conversation_id:
        _session_store[conversation_id] = session
    return session


def remove_session(session_key: str) -> None:
    """Remove session by any key (chat_id, run_id, or group_id)."""
    session = _session_store.get(session_key)
    if session:
        _session_store.pop(session.chat_id, None)
        _session_store.pop(session.run_id, None)
        _session_store.pop(session.group_id, None)
        if session.conversation_id:
            _session_store.pop(session.conversation_id, None)


def get_session_by_chat_id(chat_id: str) -> AudioSession | None:
    """Get session by chat ID (client-facing lookup)."""
    return _session_store.get(chat_id)


def get_session_by_run_id(run_id: str) -> AudioSession | None:
    """Get session by run ID."""
    return _session_store.get(run_id)


def get_session_by_group_id(group_id: str) -> AudioSession | None:
    """Get session by group ID (internal lookup)."""
    return _session_store.get(group_id)


def get_session_by_conversation_id(conversation_id: str) -> AudioSession | None:
    """Get session by conversation ID (speak endpoint lookup)."""
    return _session_store.get(conversation_id)


def rotate_run_id(session: AudioSession, new_run_id: str) -> None:
    """Rotate the run_id on an existing session (audio continuation).

    Removes the old run_id key and adds the new one, keeping chat_id
    and group_id keys intact.

    Resets ``created_at`` to anchor the MAX_SESSION_LIFETIME backstop to the
    LAST COMPLETED TURN rather than the session's first turn (VOICE2 follow-up).
    A run_id rotation happens once per completed turn (run_complete_impl), so a
    legitimately long, actively-progressing voice conversation (e.g. a >1h
    tutoring session) keeps extending its ceiling and is never force-reaped
    mid-turn — while a wedged session that completes NO turn (a within-turn
    spin / keep-alive flood that only refreshes ``last_activity`` via touch())
    never rotates, so the creation-anchored ceiling still reaps it after the
    window. Turn-completing runaway loops are independently bounded by the
    VOICE4 per-turn rate-limit breaker.
    """
    _session_store.pop(session.run_id, None)
    session.run_id = new_run_id
    session.created_at = time.monotonic()
    _session_store[new_run_id] = session


def rotate_group_id(session: AudioSession, new_group_id: str) -> None:
    """Rotate the group_id on an existing session (multi-generate reuse).

    The realtime session stays open across turns, but each
    ``/attempt/generate`` turn carries a fresh ``group_id``. Re-key the
    store so lookups (and teardown via ``remove_session(group_id)``) find
    the session under the current group_id — otherwise the old key dangles
    and the session leaks. Caller is responsible for re-keying the
    adapter's per-group task map (see ``rebind_group_id``).
    """
    if session.group_id == new_group_id:
        return
    _session_store.pop(session.group_id, None)
    session.group_id = new_group_id
    _session_store[new_group_id] = session


def get_session_by_sid(sid: str) -> AudioSession | None:
    """Get session by socket ID (disconnect cleanup only)."""
    for session in set(_session_store.values()):
        if session.sid == sid:
            return session
    return None


def get_stale_sessions(
    timeout: float = 300.0,
    max_lifetime: float = MAX_SESSION_LIFETIME,
) -> list[AudioSession]:
    """Return sessions that should be reaped: idle past ``timeout`` (default 5
    min) OR alive past ``max_lifetime`` (default 1 hour).

    The lifetime ceiling is the VOICE1 backstop: since ``touch()`` now refreshes
    ``last_activity`` on every provider event, a wedged provider keeps a session
    perpetually un-idle, so the idle check alone can never reclaim it. The
    creation-anchored ceiling (immune to ``touch()``) force-reaps it regardless.
    """
    now = time.monotonic()
    seen: set[str] = set()
    stale: list[AudioSession] = []
    for session in _session_store.values():
        if session.chat_id not in seen:
            seen.add(session.chat_id)
            idle = (now - session.last_activity) > timeout
            expired = (now - session.created_at) > max_lifetime
            if idle or expired:
                stale.append(session)
    return stale
