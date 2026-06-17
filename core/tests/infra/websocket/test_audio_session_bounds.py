"""report-22 voice subsystem: liveness + boundedness on AudioSession.

VOICE1 — ``touch()`` refreshes liveness (so the reaper sees outbound/provider
activity, not only inbound client frames).
VOICE2 — ``pending_frames`` (soft-staging buffer) is byte-capped.
VOICE3 — ``speech_audio_buffer`` has a per-frame and total cap.
"""

from __future__ import annotations

import time

import pytest

from app.infra.websocket import session_store
from app.infra.websocket.session_store import (
    MAX_FRAME_BYTES,
    PENDING_FRAMES_MAX_BYTES,
    SPEECH_BUFFER_MAX_BYTES,
    AudioSession,
    get_stale_sessions,
)


def _session() -> AudioSession:
    return AudioSession(sid="s", chat_id="c", run_id="r", group_id="g")


# ── VOICE1 — liveness ────────────────────────────────────────────────────────


def test_touch_refreshes_liveness():
    s = _session()
    s.last_activity = time.monotonic() - 10_000  # pretend long-idle
    s.touch()
    assert (time.monotonic() - s.last_activity) < 1.0


def test_reaper_skips_a_touched_session(monkeypatch):
    """A session whose liveness was refreshed (e.g. by an outbound provider
    event via touch()) must NOT be reaped, even with no inbound frames."""
    session_store._session_store.clear()
    try:
        s = _session()
        session_store._session_store[s.chat_id] = s
        s.last_activity = time.monotonic() - 10_000  # would be stale...
        assert get_stale_sessions(timeout=300.0) == [s]
        s.touch()  # ...outbound activity refreshes it
        assert get_stale_sessions(timeout=300.0) == []
    finally:
        session_store._session_store.clear()


# ── VOICE2 — pending_frames byte cap ─────────────────────────────────────────


def test_stage_pending_frame_bounds_total_bytes():
    s = _session()
    chunk = b"\x00" * 1_000_000  # 1 MB (== MAX_FRAME_BYTES, allowed)
    staged = 0
    while s.stage_pending_frame(f"k{staged}", chunk):
        staged += 1
    assert s.pending_frames_bytes <= PENDING_FRAMES_MAX_BYTES
    # The next stage past the cap is rejected (caller → 429), not buffered.
    assert s.stage_pending_frame("over", chunk) is False
    assert s.pending_frames_bytes <= PENDING_FRAMES_MAX_BYTES


def test_stage_pending_frame_rejects_oversized_frame():
    s = _session()
    assert s.stage_pending_frame("k", b"\x00" * (MAX_FRAME_BYTES + 1)) is False
    assert s.pending_frames_bytes == 0


def test_pop_pending_frames_decrements_counter():
    s = _session()
    assert s.stage_pending_frame("k", b"\x00" * 1000)
    assert s.pending_frames_bytes == 1000
    popped = s.pop_pending_frames("k")
    assert len(popped) == 1
    assert s.pending_frames_bytes == 0
    # Popping a missing key is a no-op and never goes negative.
    assert s.pop_pending_frames("missing") == []
    assert s.pending_frames_bytes == 0


# ── VOICE3 — speech_audio_buffer caps ────────────────────────────────────────


def test_buffer_speech_audio_rejects_oversized_frame():
    s = _session()
    assert s.buffer_speech_audio(b"\x00" * (MAX_FRAME_BYTES + 1)) is False
    assert len(s.speech_audio_buffer) == 0


def test_buffer_speech_audio_bounds_total():
    s = _session()
    chunk = b"\x00" * 1_000_000  # 1 MB
    added = 0
    while s.buffer_speech_audio(chunk):
        added += 1
    assert len(s.speech_audio_buffer) <= SPEECH_BUFFER_MAX_BYTES
    # Past the cap, frames are dropped (caller stops local buffering).
    assert s.buffer_speech_audio(chunk) is False
    assert len(s.speech_audio_buffer) <= SPEECH_BUFFER_MAX_BYTES
