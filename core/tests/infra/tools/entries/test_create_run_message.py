"""Tests for create_run_message — integration tests with real DB."""

import pytest
from redis.asyncio import Redis

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


async def _deps(conn, redis_client, profile_id):
    """Create session → group → run → upload for testing."""
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    upload = await create_upload(
        conn,
        redis_client, session_id=session.id,
        file_path="test/file.txt",
        mime_type="text/plain",
        size=1024,
    )
    return session, run, upload


async def test_returns_all_ids(conn, redis_client: Redis, profile_id):
    session, run, upload = await _deps(conn, redis_client, profile_id)

    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    assert result.message_id is not None
    assert result.text_id is not None
    assert result.text_upload_junction_id is not None
    assert result.message_upload_junction_id is not None


async def test_creates_message_with_correct_role(conn, redis_client, profile_id):
    session, run, upload = await _deps(conn, redis_client, profile_id)

    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="developer",
        upload_id=upload.id,
    )

    message = await get_message(conn, result.message_id, redis_client)
    assert message is not None
    assert message.run_id == run.id
    assert message.role == "developer"


async def test_creates_text_entry(conn, redis_client, profile_id):
    session, run, upload = await _deps(conn, redis_client, profile_id)

    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    text = await get_text(conn, result.text_id, redis_client)
    assert text is not None
    assert text.session_id == session.id


async def test_links_text_to_upload(conn, redis_client, profile_id):
    session, run, upload = await _deps(conn, redis_client, profile_id)

    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    row = await get_text_upload(conn, result.text_upload_junction_id, redis_client)
    assert row is not None
    assert row.text_id == result.text_id
    assert row.upload_id == upload.id


async def test_links_message_to_upload(conn, redis_client, profile_id):
    session, run, upload = await _deps(conn, redis_client, profile_id)

    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="user",
        upload_id=upload.id,
    )

    row = await get_message_upload(conn, result.message_upload_junction_id, redis_client)
    assert row is not None
    assert row.message_id == result.message_id
    assert row.upload_id == upload.id


async def test_enqueue_failure_is_logged_not_swallowed(
    conn, redis_client, profile_id, monkeypatch
):
    """A failed chat-MV refresh enqueue must be observable, not silently passed.

    The enqueue is best-effort (it must never fail the audit write), but a
    missed enqueue freezes runs_mv/messages_mv/calls_mv until another write
    re-enqueues — so the stale-data window needs a log trace rather than a
    bare ``pass``. Asserts: the write still completes (fail-soft preserved)
    AND the failure is logged at WARNING.
    """
    import app.infra.globals as globals_mod
    import app.infra.tools.entries.create_run_message as mod
    import app.utils.cache.mv_refresh_queue as mvq

    async def _boom(*_a, **_k):
        raise RuntimeError("redis enqueue down")

    # The function re-resolves the global redis client + imports enqueue_pending
    # inside the try; point the former at the test client and make the latter fail.
    monkeypatch.setattr(globals_mod, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(mvq, "enqueue_pending", _boom)

    warnings: list[str] = []
    monkeypatch.setattr(
        mod.logger, "warning", lambda msg, *a, **k: warnings.append(str(msg))
    )

    session, run, upload = await _deps(conn, redis_client, profile_id)
    result = await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    # Fail-soft: the audit write completed despite the enqueue failure.
    assert result.message_id is not None
    # ...but the failure is now observable (no longer a silent pass).
    assert any("enqueue chat-MV refresh" in w for w in warnings)


async def test_enqueue_success_does_not_warn(
    conn, redis_client, profile_id, monkeypatch
):
    """Happy path: when the enqueue succeeds it enqueues all three chat MVs
    and emits no warning."""
    import app.infra.globals as globals_mod
    import app.infra.tools.entries.create_run_message as mod
    import app.utils.cache.mv_refresh_queue as mvq

    enqueued: list[str] = []

    async def _spy(_redis, target):
        enqueued.append(target)

    monkeypatch.setattr(globals_mod, "get_redis_client", lambda: redis_client)
    monkeypatch.setattr(mvq, "enqueue_pending", _spy)

    warnings: list[str] = []
    monkeypatch.setattr(
        mod.logger, "warning", lambda msg, *a, **k: warnings.append(str(msg))
    )

    session, run, upload = await _deps(conn, redis_client, profile_id)
    await create_run_message(
        conn,
        redis_client,
        run_id=run.id,
        session_id=session.id,
        role="system",
        upload_id=upload.id,
    )

    assert enqueued == ["runs_mv", "messages_mv", "calls_mv"]
    assert warnings == []


async def test_partial_failure_rolls_back_message(
    conn, redis_client, profile_id, monkeypatch
):
    """A mid-chain failure must leave NO orphaned message row.

    ``create_run_message`` chains message → text → text_upload →
    message_upload. If a later step raises while the earlier inserts have
    already landed (asyncpg autocommits each statement), the message row
    becomes a user-visible orphan with no linked upload — corrupt state that
    can't self-heal. Wrapping the chain in ``conn.transaction()`` makes it
    atomic: the failure rolls the whole composite back.

    Pre-minting ``id`` lets us look for the would-be message row directly in
    the table (bypassing the read-through cache) and assert it never existed.
    """
    import uuid

    import app.infra.tools.entries.create_run_message as mod

    session, run, upload = await _deps(conn, redis_client, profile_id)

    pre_minted = uuid.uuid4()

    async def _boom(*_a, **_k):
        raise RuntimeError("simulated message_upload insert failure")

    # Fail the LAST insert in the chain — message/text/text_upload have
    # already been written by then.
    monkeypatch.setattr(mod, "create_message_upload", _boom)

    with pytest.raises(RuntimeError, match="message_upload insert failure"):
        await create_run_message(
            conn,
            redis_client,
            run_id=run.id,
            session_id=session.id,
            role="system",
            upload_id=upload.id,
            id=pre_minted,
        )

    # The message row must NOT survive — the whole composite rolled back.
    row = await conn.fetchrow(
        "SELECT id FROM messages_entry WHERE id = $1", pre_minted
    )
    assert row is None, "orphaned message row left behind after mid-chain failure"


async def test_multiple_messages_on_same_run(conn, redis_client, profile_id):
    """Can create multiple messages on one run (system + developer + user)."""
    session, run, _ = await _deps(conn, redis_client, profile_id)

    results = []
    for role in ["system", "developer", "user"]:
        upload = await create_upload(
            conn,
            redis_client, session_id=session.id,
            file_path=f"test/{role}.txt",
            mime_type="text/plain",
            size=100,
        )
        result = await create_run_message(
            conn,
            redis_client,
            run_id=run.id,
            session_id=session.id,
            role=role,
            upload_id=upload.id,
        )
        results.append(result)

    # All unique message IDs
    message_ids = {r.message_id for r in results}
    assert len(message_ids) == 3
