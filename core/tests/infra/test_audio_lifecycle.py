"""Tests for websocket audio lifecycle cleanup and singleton behavior."""

import pytest

import app.infra.globals as globals_mod
import app.infra.websocket.audio_lifecycle as audio_lifecycle
from app.infra.websocket.session_store import (
    _session_store,
    create_session,
    get_session_by_group_id,
)


class FakeAudioAdapter:
    def __init__(self, emitter=None):
        self.emitter = emitter
        self.stopped_sessions: list[str] = []
        self.raise_on_stop = False

    async def stop_session(self, session) -> None:
        if self.raise_on_stop:
            raise RuntimeError("adapter stop failed")
        self.stopped_sessions.append(session.group_id)


class TestAudioLifecycle:
    def setup_method(self):
        audio_lifecycle._audio_adapter = None
        _session_store.clear()
        globals_mod._voice_message_ids.clear()

    def teardown_method(self):
        audio_lifecycle._audio_adapter = None
        _session_store.clear()
        globals_mod._voice_message_ids.clear()

    def test_get_audio_adapter_creates_singleton(self):
        emitter = object()

        first = audio_lifecycle.get_audio_adapter(
            adapter_factory=FakeAudioAdapter,
            emitter=emitter,
        )
        second = audio_lifecycle.get_audio_adapter()

        assert first is second
        assert first.emitter is emitter

    @pytest.mark.asyncio
    async def test_cleanup_audio_session_removes_store_entries_and_voice_ids(self):
        session = create_session("sid-1", "chat-1", "run-1", "group-1")
        globals_mod._voice_message_ids["group-1"] = ["msg-1"]
        adapter = FakeAudioAdapter()

        await audio_lifecycle.cleanup_audio_session(session, adapter=adapter)

        assert adapter.stopped_sessions == ["group-1"]
        assert get_session_by_group_id("group-1") is None
        assert "group-1" not in globals_mod._voice_message_ids

    @pytest.mark.asyncio
    async def test_cleanup_audio_session_is_resilient_to_stop_errors(self):
        session = create_session("sid-2", "chat-2", "run-2", "group-2")
        adapter = FakeAudioAdapter()
        adapter.raise_on_stop = True

        await audio_lifecycle.cleanup_audio_session(session, adapter=adapter)

        assert get_session_by_group_id("group-2") is None
