"""Tests for create_tool_call.

CONTRACT (v1.0.46-beta+): ``create_tool_call`` returns SYNCHRONOUSLY with
``message_id`` / ``text_id`` / all ``*_junction_id`` fields left ``None`` —
the audit-persistence chain (.txt + .json receipts, upload rows, run_message,
junction INSERTs) is fired off the response critical path via
``schedule_background(_persist_audit_writes(...))``. The synchronous response
still carries ``run_id``, ``call_id``, ``call_upload_id``, ``result`` and
``error``.

These tests therefore split into two parts:
  • the synchronous return shape (asserted right off the call), and
  • the background-persisted artifacts (files + DB rows), asserted after
    draining the fire-and-forget task with ``wait_for_pending()``.

Setup runs on COMMITTED pool connections (not the rolled-back ``conn``
fixture): the background task acquires its own connection, so it can only see
data that has actually been committed — exactly mirroring production, where
``create_tool_call`` is handed a pool-acquired (auto-committing) connection.
The background task's pool/redis are passed in explicitly (``audit_pool`` /
``audit_redis``) so the fire-and-forget path runs on the test's own event loop;
the process-global pool is bound to the session-init loop and would corrupt
under asyncpg cross-loop use. Production callers pass neither and fall back to
the app-level globals.
"""

import json

import pytest

from app.infra.tools.entries import create_tool_call as create_tool_call_mod
from app.infra.tools.entries.create_tool_call import create_tool_call
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.calls.get import get_calls
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.get import get_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile
from app.tools.resources.tools.create import (
    create_tool as create_tool_resource,
)
from app.utils.async_tasks import wait_for_pending

pytestmark = pytest.mark.asyncio


# -- helpers -------------------------------------------------------------------


async def _success_tool(conn, **kwargs):
    return json.dumps({"success": True, "message": "Created"})


async def _failing_tool(conn, **kwargs):
    raise ValueError("something broke")


async def _committed_deps(pool, redis_client, *, with_tool=False):
    """Create profile + session + group (and optionally a tool) on COMMITTED
    connections.

    The background audit task reads through its own connection, so anything
    it FK-references (run/call/session) must be committed first — the
    rolled-back ``conn`` fixture would be invisible to it.
    """
    async with pool.acquire() as conn:
        profile = await create_profile(conn, redis_client)
        session = await create_session(
            conn, redis_client, profile_id=profile.id
        )
        group = await create_group(
            conn, redis_client, session_id=session.id, artifact_type="persona"
        )
        tool = await create_tool_resource(conn) if with_tool else None
    return profile, session, group, tool


async def _call(pool, redis_client, *, group, session, profile, tmp_path,
                tool_fn, arguments, tool_id=None, raise_on_error=False):
    """Invoke create_tool_call on a committed pool conn, routing the
    background audit task at the test's on-loop pool/redis."""
    async with pool.acquire() as conn:
        return await create_tool_call(
            conn,
            redis_client,
            group_id=group.id,
            session_id=session.id,
            profile_id=profile.id,
            upload_folder=tmp_path,
            tool_fn=tool_fn,
            arguments=arguments,
            tool_id=tool_id,
            raise_on_error=raise_on_error,
            audit_pool=pool,
            audit_redis=redis_client,
        )


# -- with tool_id --------------------------------------------------------------


async def test_with_tool_sync_contract(pool, redis_client, tmp_path):
    """Synchronous return: run_id/call_id present, audit ids deferred (None)."""
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )

    # Present synchronously.
    assert result.run_id is not None
    assert result.call_id is not None
    assert result.call_upload_id is not None
    assert json.loads(result.result)["success"] is True
    # Deferred to the background audit task — None on the sync response.
    assert result.message_id is None
    assert result.text_id is None
    assert result.call_upload_junction_id is None


async def test_with_tool_writes_both_files(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    await wait_for_pending()

    assert (tmp_path / "text").is_dir()
    assert (tmp_path / "call").is_dir()

    txt_files = list((tmp_path / "text").glob("*.txt"))
    json_files = list((tmp_path / "call").glob("*.json"))
    assert len(txt_files) == 1
    assert len(json_files) == 1


async def test_with_tool_json_has_correct_shape(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    await wait_for_pending()

    json_file = list((tmp_path / "call").glob("*.json"))[0]
    data = json.loads(json_file.read_text())
    assert set(data.keys()) == {"call_id", "tool_id", "arguments", "output", "raw_output"}
    assert data["arguments"] == {"name": "Dr. Smith"}
    assert data["tool_id"] == str(tool.id)


async def test_secret_key_redacted_from_receipts(pool, redis_client, tmp_path):
    """SEC2: a plaintext provider key in arguments must NOT reach the
    downloadable .json receipt or .txt upload — it is masked."""
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    secret = "sk-PLAINTEXT-SECRET-do-not-persist"
    await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"providers": [{"name": "OpenAI", "key": secret}]},
        tool_id=tool.id,
    )
    await wait_for_pending()

    json_file = list((tmp_path / "call").glob("*.json"))[0]
    json_text = json_file.read_text()
    assert secret not in json_text  # plaintext key never persisted
    data = json.loads(json_text)
    assert data["arguments"]["providers"][0]["key"] == "***REDACTED***"
    # Non-secret fields still present for audit usefulness.
    assert data["arguments"]["providers"][0]["name"] == "OpenAI"

    # And the .txt receipt likewise carries no plaintext secret.
    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    assert secret not in txt_file.read_text()


async def test_with_tool_txt_has_output(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    await wait_for_pending()

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is True


async def test_with_tool_creates_db_entries(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    await wait_for_pending()

    async with pool.acquire() as conn:
        run = await get_run(conn, result.run_id, redis_client)
        assert run is not None

        calls = await get_calls(conn, [result.call_id], redis_client, bypass_mv=True)
        assert len(calls) == 1

        # Background audit task persisted the run_message + call_upload junction.
        messages, total = await search_messages(
            conn, redis_client, run_ids=[result.run_id], bypass_mv=True
        )
        assert total >= 1

        call_uploads = await search_call_uploads(
            conn, redis_client, call_ids=[result.call_id]
        )
        assert len(call_uploads) == 1


# -- without tool_id -----------------------------------------------------------


async def test_without_tool_sync_contract(pool, redis_client, tmp_path):
    profile, session, group, _ = await _committed_deps(pool, redis_client)

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )

    assert result.run_id is not None
    assert result.call_id is None
    # Deferred to background audit task.
    assert result.message_id is None
    assert result.text_id is None
    assert result.call_upload_junction_id is None


async def test_without_tool_writes_txt_only(pool, redis_client, tmp_path):
    profile, session, group, _ = await _committed_deps(pool, redis_client)

    await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )
    await wait_for_pending()

    assert (tmp_path / "text").is_dir()
    assert not (tmp_path / "call").exists()


async def test_without_tool_creates_db_entries(pool, redis_client, tmp_path):
    profile, session, group, _ = await _committed_deps(pool, redis_client)

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"prompt": "Summarize"},
    )
    await wait_for_pending()

    async with pool.acquire() as conn:
        run = await get_run(conn, result.run_id, redis_client)
        assert run is not None

        # Background audit task persisted the run_message even without a tool.
        messages, total = await search_messages(
            conn, redis_client, run_ids=[result.run_id], bypass_mv=True
        )
        assert total >= 1


# -- error handling ------------------------------------------------------------


async def test_failing_tool_still_persists(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_failing_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    await wait_for_pending()

    assert result.run_id is not None

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is False
    assert "something broke" in data["message"]


async def test_returns_raw_result_payload(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )

    assert result.result is not None
    assert json.loads(result.result)["message"] == "Created"


async def test_composite_rolls_back_on_late_db_failure(
    pool, redis_client, tmp_path, monkeypatch
):
    """If a DB write LATE in the audit composite raises (after the upload +
    message subtree already inserted), the WHOLE composite must roll back —
    no orphaned message/upload/call rows survive.

    Pre-fix (no outer ``conn.transaction()``) asyncpg autocommits each
    statement, so the message + uploads stay committed and only the
    call_upload link is missing → a partial-write orphan. Post-fix the outer
    transaction unwinds all of them. We force the failure on the last DB write
    in the composite (``create_message_upload``, reached only after
    ``create_call_upload`` has run inside the same outer transaction).
    """
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    real_create_message_upload = create_tool_call_mod.create_message_upload

    async def _boom_create_message_upload(*args, **kwargs):
        raise RuntimeError("composite failure injected mid-write")

    monkeypatch.setattr(
        create_tool_call_mod, "create_message_upload", _boom_create_message_upload
    )

    result = await _call(
        pool, redis_client, group=group, session=session, profile=profile,
        tmp_path=tmp_path, tool_fn=_success_tool,
        arguments={"name": "Dr. Smith"}, tool_id=tool.id,
    )
    # Background audit task raises internally; schedule_background logs and
    # swallows it. Drain it, then assert nothing partial committed.
    await wait_for_pending()

    monkeypatch.setattr(
        create_tool_call_mod, "create_message_upload", real_create_message_upload
    )

    async with pool.acquire() as conn:
        # The run + call themselves are written on the SYNC path (outside the
        # audit composite) and legitimately exist — they are not part of the
        # rolled-back composite.
        run = await get_run(conn, result.run_id, redis_client)
        assert run is not None

        # The composite (uploads + message + junctions) must have fully
        # rolled back IN POSTGRES: no message and no call_upload link survives.
        # We assert the durable pg state directly (bypass_mv / bypass_cache):
        # the sub-creates' redis write_back_row calls already ran pre-fix and
        # are non-transactional, so a rolled-back pg txn leaves transient
        # cache phantoms that self-heal on TTL — out of scope for the pg
        # atomicity contract this fix establishes.
        messages, total = await search_messages(
            conn, redis_client, run_ids=[result.run_id], bypass_mv=True
        )
        assert total == 0, f"orphaned message(s) survived rollback: {total}"

        call_uploads = await search_call_uploads(
            conn, redis_client, call_ids=[result.call_id], bypass_cache=True
        )
        assert len(call_uploads) == 0, (
            f"orphaned call_upload(s) survived rollback: {len(call_uploads)}"
        )

        # And the text/call upload rows themselves rolled back.
        upload_rows = await conn.fetch(
            "SELECT id FROM uploads_entry WHERE session_id = $1 AND active = true",
            session.id,
        )
        assert len(upload_rows) == 0, (
            f"orphaned upload(s) survived rollback: {len(upload_rows)}"
        )


async def test_raise_on_error_persists_then_reraises(pool, redis_client, tmp_path):
    profile, session, group, tool = await _committed_deps(
        pool, redis_client, with_tool=True
    )

    with pytest.raises(ValueError, match="something broke"):
        await _call(
            pool, redis_client, group=group, session=session, profile=profile,
            tmp_path=tmp_path, tool_fn=_failing_tool,
            arguments={"name": "Dr. Smith"}, tool_id=tool.id,
            raise_on_error=True,
        )
    await wait_for_pending()

    txt_file = list((tmp_path / "text").glob("*.txt"))[0]
    data = json.loads(txt_file.read_text())
    assert data["success"] is False
