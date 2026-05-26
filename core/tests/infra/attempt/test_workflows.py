"""Behavior tests for `core/app/infra/attempt/workflows.py`.

Replaces a prior brittle `iscoroutinefunction(attempt_message_impl)`
implementation-shape test with real behavior assertions on the event
translators. Kept the two module-level dict assertions since they pin
the public flag→resource/connection map shape (a genuine contract).

Covers:
- `user_progress_impl` — pure dict-in → emit-out translator
- `audio_speech_delta_impl` — translator that looks up an in-memory
  session by group_id

Uses `recording_emit()` to capture emits without standing up websockets,
and the real `session_store` module-level dict for session lookups (the
store IS the production code path; mocking it would test nothing).
"""

from __future__ import annotations

import pytest

import app.infra.websocket.session_store as session_store
from app.infra.attempt.workflows import (
    GENERATE_FLAG_TO_CONNECTION,
    GENERATE_FLAG_TO_RESOURCE,
)
from app.infra.attempt.workflows import (
    audio_speech_delta_impl as _audio_speech_delta_impl,
)
from app.infra.attempt.workflows import (
    user_progress_impl as _user_progress_impl,
)
from app.infra.websocket.socket_event import recording_emit


# ─── Module-level mapping pins ─────────────────────────────────────────────


class TestGenerateFlagMappings:
    """Pin the public flag→resource and flag→connection lookup tables.
    A regression here would silently change which DB resource/connection
    a `generate_X` flag wires to."""

    def test_personas_flag_maps_to_personas_resource(self):
        assert GENERATE_FLAG_TO_RESOURCE["generate_personas"] == "personas"

    def test_personas_flag_has_connection_mapping(self):
        assert "generate_personas" in GENERATE_FLAG_TO_CONNECTION

    def test_connection_keys_are_subset_of_resource_keys(self):
        """Every flag that has a back-connection table must also have a
        resource entry. The reverse is not required: some flags
        (`generate_names`, `generate_descriptions`) map to embedded
        resources without a junction table, so they appear only in the
        resource map.

        Pins the actual asymmetry — a regression that flipped this
        (a flag with a connection but no resource) would mean we know
        how to write back the relationship but not which DB resource it
        targets."""
        resource_keys = set(GENERATE_FLAG_TO_RESOURCE.keys())
        connection_keys = set(GENERATE_FLAG_TO_CONNECTION.keys())
        orphaned = connection_keys - resource_keys
        assert orphaned == set(), (
            f"Flags in CONNECTION map but missing from RESOURCE map: {orphaned}"
        )


# ─── user_progress_impl ────────────────────────────────────────────────────


class TestUserProgressImpl:
    pytestmark = pytest.mark.asyncio

    async def test_emits_progress_with_transcript_and_item_id(self):
        emit, recorded = recording_emit()

        await _user_progress_impl(
            {
                "sid": "s-1",
                "chat_id": "chat-7",
                "item_id": "item-42",
                "transcript": "hello world",
                "rooms": ["room-a"],
            },
            emit=emit,
        )

        assert len(recorded) == 1
        event = recorded[0]
        assert event.event == "attempt.message.user.progress"
        assert event.data["sid"] == "s-1"
        assert event.data["chat_id"] == "chat-7"
        assert event.data["item_id"] == "item-42"
        assert event.data["transcript"] == "hello world"
        assert event.data["rooms"] == ["room-a"]

    async def test_defaults_transcript_to_empty_string(self):
        """A progress event without a transcript shouldn't break the wire
        contract — `transcript` is always a string on the emitted
        payload."""
        emit, recorded = recording_emit()

        await _user_progress_impl(
            {"sid": "s-1", "chat_id": "chat-1"}, emit=emit,
        )

        assert len(recorded) == 1
        assert recorded[0].data["transcript"] == ""

    async def test_silent_noop_when_sid_missing(self):
        """Without a sid the event can't be routed back to a client —
        the handler returns silently rather than emitting a malformed
        event."""
        emit, recorded = recording_emit()

        await _user_progress_impl(
            {"chat_id": "chat-1"}, emit=emit,
        )

        assert recorded == []

    async def test_silent_noop_when_chat_id_missing(self):
        emit, recorded = recording_emit()

        await _user_progress_impl({"sid": "s-1"}, emit=emit)

        assert recorded == []


# ─── audio_speech_delta_impl ───────────────────────────────────────────────


class TestAudioSpeechDeltaImpl:
    pytestmark = pytest.mark.asyncio

    @pytest.fixture(autouse=True)
    def _clear_session_store(self):
        """The session store is module-global; clear it between tests so
        a stale session from a sibling test can't leak in."""
        session_store._session_store.clear()
        yield
        session_store._session_store.clear()

    async def test_emits_progress_when_session_and_item_present(self):
        session_store.create_session(
            sid="s-1",
            chat_id="chat-1",
            run_id="run-1",
            group_id="grp-1",
        )

        emit, recorded = recording_emit()
        await _audio_speech_delta_impl(
            {
                "group_id": "grp-1",
                "item_id": "item-9",
                "transcript": "speech sample",
            },
            emit=emit,
        )

        assert len(recorded) == 1
        event = recorded[0]
        assert event.event == "attempt.response.progress"
        assert event.data["sid"] == "s-1"
        assert event.data["chat_id"] == "chat-1"
        assert event.data["item_id"] == "item-9"
        assert event.data["transcript"] == "speech sample"

    async def test_silent_noop_when_group_id_missing(self):
        emit, recorded = recording_emit()

        await _audio_speech_delta_impl(
            {"item_id": "item-9"}, emit=emit,
        )

        assert recorded == []

    async def test_silent_noop_when_no_session_for_group(self):
        """Group id present but no session registered — handler returns
        silently. Guards against a regression that would NPE or emit a
        malformed event with a None session."""
        emit, recorded = recording_emit()

        await _audio_speech_delta_impl(
            {"group_id": "unknown-group", "item_id": "item-9"},
            emit=emit,
        )

        assert recorded == []

    async def test_silent_noop_when_item_id_missing(self):
        session_store.create_session(
            sid="s-1",
            chat_id="chat-1",
            run_id="run-1",
            group_id="grp-1",
        )

        emit, recorded = recording_emit()
        await _audio_speech_delta_impl({"group_id": "grp-1"}, emit=emit)

        assert recorded == []

    async def test_defaults_transcript_to_empty_string(self):
        session_store.create_session(
            sid="s-1",
            chat_id="chat-1",
            run_id="run-1",
            group_id="grp-1",
        )

        emit, recorded = recording_emit()
        await _audio_speech_delta_impl(
            {"group_id": "grp-1", "item_id": "item-9"}, emit=emit,
        )

        assert len(recorded) == 1
        assert recorded[0].data["transcript"] == ""
