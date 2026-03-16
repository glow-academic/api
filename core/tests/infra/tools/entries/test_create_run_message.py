"""Tests for create_run_message — integration tests with real DB."""

import pytest

from app.infra.tools.entries.create_run_message import create_run_message
from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.texts.get import get_text
from app.tools.entries.uploads.create import create_upload

pytestmark = pytest.mark.asyncio


async def _deps(conn, profile_id):
    """Create session → group → run → upload for testing."""
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(
        conn, group_id=group.id, session_id=session.id, profiles_id=profile_id
    )
    upload = await create_upload(
        conn,
        session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, run, upload


async def test_returns_all_ids(conn, profile_id):
    session, run, upload = await _deps(conn, profile_id)

    result = await create_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    assert result.message_id is not None
    assert result.text_id is not None
    assert result.text_upload_junction_id is not None
    assert result.message_upload_junction_id is not None


async def test_creates_message_with_correct_role(conn, profile_id):
    session, run, upload = await _deps(conn, profile_id)

    result = await create_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="developer",
        upload_id=upload.id,
    )

    message = await get_message(conn, result.message_id)
    assert message is not None
    assert message.run_id == run.id
    assert message.role == "developer"


async def test_creates_text_entry(conn, profile_id):
    session, run, upload = await _deps(conn, profile_id)

    result = await create_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    text = await get_text(conn, result.text_id)
    assert text is not None
    assert text.session_id == session.id


async def test_links_text_to_upload(conn, profile_id):
    session, run, upload = await _deps(conn, profile_id)

    result = await create_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    row = await get_text_upload(conn, result.text_upload_junction_id)
    assert row is not None
    assert row.text_id == result.text_id
    assert row.upload_id == upload.id


async def test_links_message_to_upload(conn, profile_id):
    session, run, upload = await _deps(conn, profile_id)

    result = await create_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="user",
        upload_id=upload.id,
    )

    row = await get_message_upload(conn, result.message_upload_junction_id)
    assert row is not None
    assert row.message_id == result.message_id
    assert row.upload_id == upload.id


async def test_multiple_messages_on_same_run(conn, profile_id):
    """Can create multiple messages on one run (system + developer + user)."""
    session, run, _ = await _deps(conn, profile_id)

    results = []
    for role in ["system", "developer", "user"]:
        upload = await create_upload(
            conn,
            session_id=session.id,
            file_path=f"test/{role}.txt",
            mime_type="text/plain",
            size=100,
        )
        result = await create_run_message(
            conn,
            run_id=run.id,
            session_id=session.id,
            role=role,
            upload_id=upload.id,
        )
        results.append(result)

    # All unique message IDs
    message_ids = {r.message_id for r in results}
    assert len(message_ids) == 3
