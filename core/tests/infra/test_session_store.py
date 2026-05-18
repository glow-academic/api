"""Tests for websocket audio session store."""

import time

from app.infra.websocket.session_store import (
    _session_store,
    create_session,
    get_session_by_chat_id,
    get_session_by_group_id,
    get_session_by_run_id,
    get_session_by_sid,
    get_stale_sessions,
    remove_session,
    rotate_run_id,
)


class TestSessionStore:
    def setup_method(self):
        _session_store.clear()

    def teardown_method(self):
        _session_store.clear()

    def test_create_session_indexes_by_chat_run_and_group(self):
        session = create_session(
            sid="sid-1",
            chat_id="chat-1",
            run_id="run-1",
            group_id="group-1",
            artifact_type="chat",
            resource_type="personas",
            metadata={"mode": "audio"},
        )

        assert get_session_by_chat_id("chat-1") is session
        assert get_session_by_run_id("run-1") is session
        assert get_session_by_group_id("group-1") is session
        assert session.metadata == {"mode": "audio"}
        assert session.artifact_type == "chat"
        assert session.resource_type == "personas"

    def test_remove_session_clears_all_indexes(self):
        create_session("sid-2", "chat-2", "run-2", "group-2")

        remove_session("run-2")

        assert get_session_by_chat_id("chat-2") is None
        assert get_session_by_run_id("run-2") is None
        assert get_session_by_group_id("group-2") is None

    def test_rotate_run_id_updates_run_lookup_only(self):
        session = create_session("sid-3", "chat-3", "run-3", "group-3")

        rotate_run_id(session, "run-3b")

        assert get_session_by_run_id("run-3") is None
        assert get_session_by_run_id("run-3b") is session
        assert get_session_by_chat_id("chat-3") is session
        assert get_session_by_group_id("group-3") is session

    def test_get_session_by_sid_scans_unique_sessions(self):
        session = create_session("sid-4", "chat-4", "run-4", "group-4")
        assert get_session_by_sid("sid-4") is session
        assert get_session_by_sid("missing-sid") is None

    def test_get_stale_sessions_dedupes_and_filters_by_timeout(self):
        stale = create_session("sid-5", "chat-5", "run-5", "group-5")
        fresh = create_session("sid-6", "chat-6", "run-6", "group-6")
        stale.last_activity = time.monotonic() - 600
        fresh.last_activity = time.monotonic()

        result = get_stale_sessions(timeout=300)

        assert result == [stale]
