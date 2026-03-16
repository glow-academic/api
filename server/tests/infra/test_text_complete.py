"""Tests for text_complete_impl using the real run-message persistence path."""

from __future__ import annotations

import pytest
from tests.helpers import nonexistent_id

from app.infra.websocket.socket_event import recording_emit
from app.infra.websocket.text_complete_impl import text_complete_impl
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.uploads.get import get_upload

pytestmark = pytest.mark.asyncio


async def _run_deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(
        conn,
        group_id=group.id,
        session_id=session.id,
        profiles_id=profile_id,
    )
    return session, run


class TestTextCompleteImpl:
    async def test_non_text_complete_skipped(self, conn):
        emit, events = recording_emit()

        await text_complete_impl({"event_type": "other"}, emit=emit, conn=conn)

        assert events == []

    async def test_no_run_id_skipped(self, conn):
        emit, events = recording_emit()

        await text_complete_impl(
            {
                "event_type": "text_complete",
                "session_id": str(nonexistent_id()),
                "text": "hello",
            },
            emit=emit,
            conn=conn,
        )

        assert events == []

    async def test_no_session_id_skipped(self, conn):
        emit, events = recording_emit()

        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": str(nonexistent_id()),
                "text": "hello",
            },
            emit=emit,
            conn=conn,
        )

        assert events == []

    async def test_empty_text_skipped(self, conn):
        emit, events = recording_emit()

        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": str(nonexistent_id()),
                "session_id": str(nonexistent_id()),
                "text": "",
            },
            emit=emit,
            conn=conn,
        )

        assert events == []

    async def test_persists_assistant_message(self, conn, profile_id, tmp_path):
        emit, events = recording_emit()
        session, run = await _run_deps(conn, profile_id)

        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": str(run.id),
                "session_id": str(session.id),
                "text": "Hello world",
            },
            emit=emit,
            conn=conn,
            upload_folder=tmp_path,
        )

        items, total_count = await search_messages(
            conn,
            run_ids=[run.id],
            bypass_mv=True,
        )

        assert events == []
        assert total_count == 1
        assert len(items) == 1
        assert items[0].role == "assistant"
        assert len(items[0].text_upload_ids) == 1

        upload = await get_upload(conn, items[0].text_upload_ids[0])
        stored_path = tmp_path / upload.file_path
        assert stored_path.exists()
        assert stored_path.read_text() == "Hello world"

    async def test_persist_error_does_not_raise(self, conn):
        emit, events = recording_emit()

        await text_complete_impl(
            {
                "event_type": "text_complete",
                "run_id": str(nonexistent_id()),
                "session_id": str(nonexistent_id()),
                "text": "Hello world",
            },
            emit=emit,
            conn=conn,
        )

        assert events == []
