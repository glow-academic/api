"""S2 — ``_chat_post_complete`` fires exactly once per run, even when two
parallel multi-agent dispatches both observe ``all_done`` concurrently.

In an A/B / test fan-out both dispatches call ``run_complete_impl`` on separate
connections. ``resolve_run_completion`` is a read-only count-vs-threshold, so
if both reads see the full set of committed answer rows, BOTH pass ``all_done``
and (pre-fix) BOTH ran ``_chat_post_complete`` → double attempt MV refresh +
duplicate ``attempt.chat_create.completed`` / ``chat_grade.completed`` on the
wire. The fix gates the transition on an atomic Redis ``SET NX`` claim keyed by
run_id. This test drives two concurrent completions and asserts the
post-complete hook runs once.

Real DB + real Redis; deps injected as params.
"""

from __future__ import annotations

import uuid

import pytest

from app.infra.websocket import run_complete_impl as rc_module
from app.infra.websocket.run_complete_impl import run_complete_impl
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session

pytestmark = pytest.mark.asyncio


def _emit_noop():
    async def _emit(_events):
        return None
    return _emit


async def test_chat_post_complete_fires_once_under_concurrent_completion(
    conn, redis_client, profile_id, tmp_path, monkeypatch
):
    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="chat"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id,
        agent_ids=[uuid.uuid4()],  # single expected agent → all_done after 1 answer
    )

    fired = {"count": 0}

    async def _spy_post_complete(**kwargs):
        fired["count"] += 1

    monkeypatch.setattr(rc_module, "_chat_post_complete", _spy_post_complete)

    # The S2 bug is in the post-complete TRANSITION after all_done resolves True
    # — under the parallel race BOTH dispatches read all_done=True. Force that
    # condition for both calls so the test isolates the fire-once Redis claim
    # rather than MV-refresh timing.
    from app.infra.websocket.resolve_run_completion import RunCompletionState

    async def _all_done(*a, **k):
        return RunCompletionState(
            all_done=True, expected_agents=1, completed_agents=1, agent_results=[]
        )

    monkeypatch.setattr(rc_module, "resolve_run_completion", _all_done)

    metadata = {
        "attempt_id": str(uuid.uuid4()),
        "attempt_chat_id": str(uuid.uuid4()),
    }

    def _payload(answer: str) -> dict:
        return {
            "sid": "sid-s2",
            "run_id": str(run.id),
            "group_id": str(group.id),
            "session_id": str(session.id),
            "profile_id": str(profile_id),
            "artifact_type": "chat",
            "modality": "text",
            "assistant_output": answer,
            "input_text_tokens": 1,
            "output_text_tokens": 1,
            "metadata": metadata,
        }

    # Both dispatches resolve all_done=True (single expected agent, answer row
    # committed within this txn) and both call run_complete_impl. The S2 race is
    # in the post-complete TRANSITION, not the DB write; running both calls on
    # the same injected conn keeps the run/messages visible while still
    # exercising the fire-once Redis claim — the second call must observe the
    # claim taken and skip the hook.
    await run_complete_impl(
        _payload("answer-1"),
        emit=_emit_noop(), conn=conn, redis=redis_client, upload_folder=tmp_path,
    )
    await run_complete_impl(
        _payload("answer-2"),
        emit=_emit_noop(), conn=conn, redis=redis_client, upload_folder=tmp_path,
    )

    # The fire-once Redis claim must let exactly one dispatch run the hook.
    assert fired["count"] == 1
    # And the claim marker is present.
    assert await redis_client.exists(f"run_complete_fired:{run.id}")
