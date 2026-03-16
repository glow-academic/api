"""Tests for persist_run_message using real DB and filesystem writes."""

import pytest

from app.infra.websocket.persist_run_message import persist_run_message
from app.tools.entries.groups.create import create_group
from app.tools.entries.message_uploads.get import get_message_upload
from app.tools.entries.messages.get import get_message
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.entries.text_uploads.get import get_text_upload
from app.tools.entries.texts.get import get_text
from app.tools.entries.uploads.get import get_upload
from app.tools.resources.agents.create import create_agent

pytestmark = pytest.mark.asyncio


async def _run_deps(conn, profile_id):
    session = await create_session(conn, profile_id=profile_id)
    group = await create_group(conn, session_id=session.id)
    run = await create_run(
        conn, group_id=group.id, session_id=session.id, profiles_id=profile_id
    )
    return session, run


async def test_persist_run_message_writes_file_and_rows(conn, profile_id, tmp_path):
    session, run = await _run_deps(conn, profile_id)

    result = await persist_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="developer",
        content="Hello from persisted text",
        upload_folder=tmp_path,
    )

    message = await get_message(conn, result.message_id)
    text = await get_text(conn, result.text_id)
    upload_junction = await get_message_upload(conn, result.message_upload_junction_id)
    text_upload_junction = await get_text_upload(conn, result.text_upload_junction_id)
    upload = await get_upload(conn, upload_junction.upload_id)
    stored_path = tmp_path / upload.file_path

    assert message.role == "developer"
    assert text.session_id == session.id
    assert upload_junction.message_id == result.message_id
    assert text_upload_junction.text_id == result.text_id
    assert stored_path.exists()
    assert stored_path.read_text() == "Hello from persisted text"


async def test_persist_run_message_links_agent_ids(
    conn, profile_id, redis_client, tmp_path
):
    session, run = await _run_deps(conn, profile_id)
    agent = await create_agent(conn, name="persist-agent", redis=redis_client)

    result = await persist_run_message(
        conn,
        run_id=run.id,
        session_id=session.id,
        role="system",
        content="System prompt",
        upload_folder=tmp_path,
        agent_ids=[agent.id],
    )

    message = await get_message(conn, result.message_id)
    assert message.id == result.message_id
