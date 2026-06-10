"""Atomicity of the run_complete turn write (reasoning + answer + tokens).

``run_complete_impl`` persists three logically-coupled rows for one model
turn: the reasoning trace, the final answer, and the token-accounting row.
These must land together or not at all — a mid-turn failure must NOT leave a
committed reasoning trace with no answer, nor messages with no token row.

Real DB + filesystem; deps injected (conn/redis/upload_folder as params).
"""

import pytest

from app.infra.websocket import run_complete_impl as rc_module
from app.infra.websocket.run_complete_impl import run_complete_impl
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


async def _run_deps(conn, redis_client, profile_id):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id
    )
    return session, group, run


def _emit_noop():
    async def _emit(_events):
        return None

    return _emit


async def _count_messages(conn, run_id):
    """Direct DB read (bypasses the hedge cache, which is not txn-bound)."""
    total = await conn.fetchval(
        "SELECT count(*) FROM messages_entry WHERE run_id = $1", run_id
    )
    reasoning = await conn.fetchval(
        "SELECT count(*) FROM messages_entry WHERE run_id = $1 AND reasoning = true",
        run_id,
    )
    return total, reasoning


async def test_happy_turn_persists_reasoning_answer_and_token(
    conn, redis_client, profile_id, tmp_path
):
    session, group, run = await _run_deps(conn, redis_client, profile_id)

    await run_complete_impl(
        {
            "sid": "sid-happy",
            "run_id": str(run.id),
            "group_id": str(group.id),
            "session_id": str(session.id),
            "artifact_type": "persona",
            "modality": "text",
            "reasoning_output": "thinking step by step",
            "assistant_output": "the final answer",
            "input_text_tokens": 11,
            "output_text_tokens": 22,
        },
        emit=_emit_noop(),
        conn=conn,
        redis=redis_client,
        upload_folder=tmp_path,
    )

    total, reasoning = await _count_messages(conn, run.id)
    token_count = await conn.fetchval(
        "SELECT count(*) FROM tokens_entry WHERE run_id = $1", run.id
    )

    assert total == 2  # reasoning + answer both landed
    assert reasoning == 1  # exactly one reasoning trace
    assert token_count == 1  # token-accounting row landed


async def test_mid_turn_failure_rolls_back_reasoning_trace(
    conn, redis_client, profile_id, tmp_path, monkeypatch
):
    """Inject a failure on the answer write — the already-written reasoning
    trace must roll back, leaving NO orphaned reasoning row in the DB."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)

    real_persist = rc_module.persist_run_message

    async def _flaky_persist(*args, **kwargs):
        # Let the reasoning write succeed; fail the answer write so the
        # whole turn must unwind.
        if kwargs.get("reasoning"):
            return await real_persist(*args, **kwargs)
        raise RuntimeError("injected answer-write failure")

    monkeypatch.setattr(rc_module, "persist_run_message", _flaky_persist)

    # run_complete_impl swallows the write failure (logs it) and continues.
    await run_complete_impl(
        {
            "sid": "sid-fail",
            "run_id": str(run.id),
            "group_id": str(group.id),
            "session_id": str(session.id),
            "artifact_type": "persona",
            "modality": "text",
            "reasoning_output": "thinking that should not survive",
            "assistant_output": "answer that fails to write",
            "input_text_tokens": 5,
            "output_text_tokens": 7,
        },
        emit=_emit_noop(),
        conn=conn,
        redis=redis_client,
        upload_folder=tmp_path,
    )

    total, reasoning = await _count_messages(conn, run.id)
    token_count = await conn.fetchval(
        "SELECT count(*) FROM tokens_entry WHERE run_id = $1", run.id
    )

    # Atomic: the reasoning trace rolled back with the failed answer.
    assert reasoning == 0
    assert total == 0
    assert token_count == 0
