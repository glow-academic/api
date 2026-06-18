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
    rotate_run_id,
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


def test_reaper_force_reaps_session_past_max_lifetime():
    """VOICE1 backstop: ``touch()`` keeps ``last_activity`` perpetually fresh, so
    a wedged-but-busy provider can never be reaped on idle alone. The hard
    max-lifetime ceiling — anchored on ``created_at`` and immune to touch() —
    force-reaps it once the session has been alive past the ceiling."""
    session_store._session_store.clear()
    try:
        s = _session()
        session_store._session_store[s.chat_id] = s
        s.touch()  # actively touched → idle check alone never fires
        assert get_stale_sessions(timeout=300.0, max_lifetime=3600.0) == []
        # Pretend the session was created just past the lifetime ceiling, while
        # STILL being actively touched (so only the lifetime branch can catch it).
        s.created_at = time.monotonic() - 3601.0
        s.touch()
        assert get_stale_sessions(timeout=300.0, max_lifetime=3600.0) == [s]
    finally:
        session_store._session_store.clear()


def test_created_at_is_not_refreshed_by_touch():
    """``touch()`` bumps liveness but must leave ``created_at`` fixed — otherwise
    the max-lifetime backstop would be defeated by the same event flood that
    defeats the idle check."""
    s = _session()
    created = s.created_at
    s.last_activity = created - 5.0
    s.touch()
    assert s.created_at == created
    assert s.last_activity > created


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


# ── VOICE2 — max-lifetime backstop must not reap a long, progressing session ──


def test_rotate_run_id_resets_created_at_extends_lifetime():
    """A completed-turn rotation refreshes created_at so the MAX_SESSION_LIFETIME
    backstop is anchored to the LAST completed turn — a >1h actively-progressing
    voice conversation is not force-reaped mid-turn (regression: created_at was
    pinned to the first turn)."""
    session_store._session_store.clear()
    try:
        s = _session()
        session_store._session_store[s.chat_id] = s
        # Pretend the session started well past the lifetime ceiling, but is
        # still actively touched (so only the lifetime branch could reap it).
        s.created_at = time.monotonic() - 4000.0
        s.touch()
        assert get_stale_sessions(timeout=300.0, max_lifetime=3600.0) == [s]
        # A completed turn rotates the run_id → created_at refreshed → not reaped.
        rotate_run_id(s, "new-run-id")
        assert (time.monotonic() - s.created_at) < 1.0
        assert get_stale_sessions(timeout=300.0, max_lifetime=3600.0) == []
    finally:
        session_store._session_store.clear()


def test_wedged_session_without_rotation_still_reaped():
    """Companion: a session that completes NO turn (no rotation) keeps its
    original created_at, so the lifetime backstop still reaps it — the VOICE1
    wedged-session protection is preserved."""
    session_store._session_store.clear()
    try:
        s = _session()
        session_store._session_store[s.chat_id] = s
        s.created_at = time.monotonic() - 4000.0
        s.touch()  # actively touched, but never rotates (no completed turn)
        assert get_stale_sessions(timeout=300.0, max_lifetime=3600.0) == [s]
    finally:
        session_store._session_store.clear()
