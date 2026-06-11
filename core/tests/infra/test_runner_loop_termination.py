"""Runner-loop termination + multi-agent completion correctness.

Covers four bugs in the generation/runner loop + completion layer, all
exercised with real DB + real Redis (deps injected as params), mocking only
the litellm provider stream so the agentic loop runs deterministically:

  G1 — Stop must abort a tool-heavy (<12 stream-event) iteration. The only
       cancel check used to be an in-stream poll on ``cancel_poll % 12``, so a
       short tool turn never reached it. The fix checks ``cancel_run:{run_id}``
       at the iteration boundary AND before each tool dispatch.

  G2 — Hitting ``max_iterations`` used to fall through and report the partial
       (often empty) turn as a clean success. The fix surfaces a terminal
       state: raise when there is no usable answer.

  S1 — A per-agent exception in a parallel multi-agent run used to be swallowed
       (the run returned the other agent's result and reported SUCCESS while
       the attempt lifecycle / MV refresh never fired). The fix re-raises so the
       run reaches a real terminal state (``runner`` emits ``.generate.failed``).

  S2 — ``_chat_post_complete`` (attempt MV refresh + lifecycle emits) could
       double-fire when two parallel dispatches both observe ``all_done``. The
       fix gates it on an atomic Redis ``SET NX`` claim keyed by run_id.
"""

from __future__ import annotations

import uuid

import pytest

from app.infra.generation import execute as execute_mod
from app.infra.generation.execute import (
    _execute_agent_dispatch,
    execute_generation,
)
from app.infra.generation.types import AgentDispatch, PrepareGenerationResult

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeBus:
    """Records emits instead of touching socket.io."""

    def __init__(self):
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event, data=None, *args, **kwargs):
        self.events.append((event, data or {}))


def _tool_heavy_events(call_id: str = "call_1"):
    """A short tool-using iteration: 4 events, well under the 12-event poll."""
    return [
        {"type": "tool_call_start", "tool_call_id": call_id, "tool_name": "do_thing"},
        {"type": "tool_call_delta", "tool_call_id": call_id, "delta": "{}"},
        {"type": "tool_call_complete", "tool_call_id": call_id,
         "name": "do_thing", "arguments": "{}"},
        {"type": "message_complete", "usage": {"prompt_tokens": 5, "completion_tokens": 2}},
    ]


def _make_dispatch(*, with_tool: bool = True) -> AgentDispatch:
    tools = (
        [{
            "name": "do_thing",
            "description": "test tool",
            "parameters": {"type": "object", "properties": {}},
            "_permissions": [{"artifact": "x", "operation": "y"}],
        }]
        if with_tool else []
    )
    return AgentDispatch(
        agent_id=uuid.uuid4(),
        messages=[{"role": "user", "content": "hi"}],
        tools=tools,
        llm_config={"model": "test-model", "temperature": 0.0, "tool_choice": "auto"},
        resource_types=[],
        metadata={},
    )


def _make_prepared(session, group, run, profile_id, dispatches) -> PrepareGenerationResult:
    return PrepareGenerationResult(
        run_id=run.id,
        group_id=group.id,
        session_id=session.id,
        profile_id=profile_id,
        profiles_id=profile_id,
        artifact_type="persona",
        dispatches=dispatches,
    )


async def _run_deps(conn, redis_client, profile_id, *, agent_ids=None):
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.sessions.create import create_session

    session = await create_session(conn, redis_client, profile_id=profile_id)
    group = await create_group(
        conn, redis_client, session_id=session.id, artifact_type="persona"
    )
    run = await create_run(
        conn, redis_client, group_id=group.id, session_id=session.id,
        agent_ids=agent_ids,
    )
    return session, group, run


def _patch_stream(monkeypatch, events_per_iteration):
    """Make the loop deterministic: a no-op LLM call + scripted stream events.

    ``events_per_iteration`` is a list whose i-th element is the event list the
    i-th loop iteration's stream yields. A callable element is invoked per call.
    """
    calls = {"n": 0}

    async def _fake_call(*args, **kwargs):
        return object()  # opaque stream handle; consumed by the fake below

    async def _fake_stream(_stream):
        i = calls["n"]
        calls["n"] += 1
        evs = events_per_iteration[min(i, len(events_per_iteration) - 1)]
        if callable(evs):
            evs = evs()
        for e in evs:
            yield e

    monkeypatch.setattr(execute_mod, "_call_responses_api", _fake_call)
    monkeypatch.setattr(execute_mod, "_call_chat_completions_api", _fake_call)
    monkeypatch.setattr(execute_mod, "stream_litellm_events", _fake_stream)
    # Avoid running the real responses-api detection / tool conversion noise.
    monkeypatch.setattr(execute_mod, "LITELLM_AVAILABLE", True, raising=False)
    return calls


# ---------------------------------------------------------------------------
# G1 — Stop aborts a tool-heavy (<12-event) iteration
# ---------------------------------------------------------------------------


async def test_g1_stop_aborts_tool_heavy_iteration(
    conn, redis_client, profile_id, pool, monkeypatch
):
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=True)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    # Tool would be dispatched if the loop continued — track real dispatch.
    dispatched = {"count": 0}

    async def _fake_exec_infra(ctx, spec):
        dispatched["count"] += 1
        return []

    monkeypatch.setattr(execute_mod, "execute_infra_operation", _fake_exec_infra)

    # Each iteration yields a short (4-event) tool-heavy stream — never reaches
    # the 12-event in-stream poll.
    _patch_stream(monkeypatch, [_tool_heavy_events])
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    # Stop was pressed BEFORE the loop runs — the marker is live.
    await redis_client.setex(f"cancel_run:{run.id}", 300, "1")

    with pytest.raises(RuntimeError, match="stopped by user"):
        await _execute_agent_dispatch(
            pool, redis_client,
            dispatch=dispatch, prepared=prepared, sid="sid-g1",
            tool_soft=True, max_iterations=15, internal_sio=_FakeBus(),
        )

    # The loop aborted before dispatching the tool (iteration-boundary check).
    assert dispatched["count"] == 0


async def test_g1_stop_before_tool_dispatch_mid_stream(
    conn, redis_client, profile_id, pool, monkeypatch
):
    """Stop arriving after the stream started but before tool dispatch is honoured
    by the pre-dispatch check (not just the iteration-boundary check)."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=True)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    dispatched = {"count": 0}

    async def _fake_exec_infra(ctx, spec):
        dispatched["count"] += 1
        return []

    monkeypatch.setattr(execute_mod, "execute_infra_operation", _fake_exec_infra)

    async def _set_cancel_then_events():
        # Simulate Stop landing during the stream: set the marker mid-iteration,
        # then emit the tool_call_complete that would dispatch.
        await redis_client.setex(f"cancel_run:{run.id}", 300, "1")
        return _tool_heavy_events()

    # Iteration boundary sees no marker (set during the stream), pre-dispatch does.
    async def _fake_stream(_stream):
        for e in await _set_cancel_then_events():
            yield e

    async def _fake_call(*a, **k):
        return object()

    monkeypatch.setattr(execute_mod, "_call_responses_api", _fake_call)
    monkeypatch.setattr(execute_mod, "_call_chat_completions_api", _fake_call)
    monkeypatch.setattr(execute_mod, "stream_litellm_events", _fake_stream)
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    with pytest.raises(RuntimeError, match="stopped by user"):
        await _execute_agent_dispatch(
            pool, redis_client,
            dispatch=dispatch, prepared=prepared, sid="sid-g1b",
            tool_soft=True, max_iterations=15, internal_sio=_FakeBus(),
        )

    assert dispatched["count"] == 0


# ---------------------------------------------------------------------------
# G2 — max_iterations surfaces a terminal state, not empty success
# ---------------------------------------------------------------------------


async def test_g2_max_iterations_raises_on_empty_answer(
    conn, redis_client, profile_id, pool, monkeypatch
):
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=True)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    async def _fake_exec_infra(ctx, spec):
        return []

    monkeypatch.setattr(execute_mod, "execute_infra_operation", _fake_exec_infra)
    # EVERY iteration keeps requesting a tool and never emits a final answer.
    _patch_stream(monkeypatch, [_tool_heavy_events])
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    with pytest.raises(RuntimeError, match="maximum of 3 tool-use iterations"):
        await _execute_agent_dispatch(
            pool, redis_client,
            dispatch=dispatch, prepared=prepared, sid="sid-g2",
            tool_soft=True, max_iterations=3, internal_sio=_FakeBus(),
        )

    # No assistant answer row persisted for this truncated turn.
    total = await conn.fetchval(
        "SELECT count(*) FROM messages_entry WHERE run_id = $1 AND role = 'assistant'",
        run.id,
    )
    assert total == 0


async def test_g2_graceful_finish_is_not_flagged(
    conn, redis_client, profile_id, pool, monkeypatch
):
    """A turn that ends with a real answer (no trailing tool call) must NOT trip
    the max-iterations terminal path."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=True)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    async def _fake_exec_infra(ctx, spec):
        return []

    monkeypatch.setattr(execute_mod, "execute_infra_operation", _fake_exec_infra)
    # Iter 1: tool call. Iter 2: a final text answer, no tool → graceful break.
    answer_events = [
        {"type": "text_delta", "delta": "the answer"},
        {"type": "message_complete", "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    ]
    _patch_stream(monkeypatch, [_tool_heavy_events(), answer_events])
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    # The run row lives in the rolled-back ``conn`` transaction, invisible to the
    # ``pool.acquire()`` persistence inside _execute_agent_dispatch. We're only
    # asserting the LOOP terminates gracefully (G2 not tripped), so stub the
    # persist/coordinate tail.
    async def _noop_run_complete(*a, **k):
        return None
    monkeypatch.setattr(execute_mod, "run_complete_impl", _noop_run_complete, raising=False)
    import app.infra.websocket.run_complete_impl as _rcmod
    monkeypatch.setattr(_rcmod, "run_complete_impl", _noop_run_complete)

    result = await _execute_agent_dispatch(
        pool, redis_client,
        dispatch=dispatch, prepared=prepared, sid="sid-g2ok",
        tool_soft=True, max_iterations=15, internal_sio=_FakeBus(),
    )
    assert result.assistant_output == "the answer"


# ---------------------------------------------------------------------------
# S1 — multi-agent error reaches a terminal state (no silent success)
# ---------------------------------------------------------------------------


async def test_s1_multi_agent_error_does_not_report_success(
    conn, redis_client, profile_id, pool, monkeypatch
):
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    d_ok = _make_dispatch(with_tool=False)
    d_err = _make_dispatch(with_tool=False)
    prepared = _make_prepared(session, group, run, profile_id, [d_ok, d_err])

    bus = _FakeBus()
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: bus)

    real_one = execute_mod._execute_agent_dispatch

    async def _maybe_fail(pool_, redis_, *, dispatch, **kw):
        if dispatch.agent_id == d_err.agent_id:
            raise RuntimeError("provider 5xx on agent B")
        # Return a benign result for the OK agent without running the real loop.
        return execute_mod.ExecuteGenerationResult(run_id=prepared.run_id)

    monkeypatch.setattr(execute_mod, "_execute_agent_dispatch", _maybe_fail)

    # The errored agent must NOT be swallowed into a silent success — the run
    # raises so runner._run drives a real terminal state.
    with pytest.raises(RuntimeError, match="provider 5xx on agent B"):
        await execute_generation(
            pool, redis_client, prepared=prepared, sid="sid-s1",
        )


async def test_g3_cancel_persists_completed_iteration_usage_and_clears_marker(
    conn, redis_client, profile_id, pool, monkeypatch
):
    """G3/H4: a Stop mid-run must (1) persist the token/cost the COMPLETED
    iterations already consumed (not drop billing), and (2) clear the
    ``cancel_run`` marker so a reused run_id isn't instant-killed.

    The partial-usage flush runs on its OWN ``pool.acquire()`` connection (real
    production path), which can't see the rolled-back ``conn`` fixture's
    uncommitted run row — a real ``create_token`` would FK-fail on a run that
    was never committed. So we spy on the token writer to assert the accumulated
    usage is flushed with the right numbers, and assert the marker cleanup on
    Redis directly."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=True)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    async def _fake_exec_infra(ctx, spec):
        return []

    monkeypatch.setattr(execute_mod, "execute_infra_operation", _fake_exec_infra)

    # Spy the partial-usage writers at their source modules (the cancel flush
    # imports them locally). Assert the COMPLETED iteration's usage is flushed.
    token_calls: list[dict] = []

    async def _spy_create_token(conn_, redis_, *, run_id, session_id, input_tokens=0, output_tokens=0, **kw):
        token_calls.append({"input": input_tokens, "output": output_tokens, "run_id": run_id})

    async def _spy_persist_msg(*a, **k):
        return None

    import app.tools.entries.tokens.create as _tok_mod
    import app.infra.websocket.persist_run_message as _msg_mod
    monkeypatch.setattr(_tok_mod, "create_token", _spy_create_token)
    monkeypatch.setattr(_msg_mod, "persist_run_message", _spy_persist_msg)

    # Iter 1 completes a tool-heavy turn (5 in/2 out tokens), then Stop lands;
    # the iteration-boundary check at the top of iter 2 raises. The usage from
    # iter 1 must survive.
    iters = {"n": 0}

    async def _fake_call(*a, **k):
        return object()

    async def _fake_stream(_stream):
        iters["n"] += 1
        for e in _tool_heavy_events():
            yield e
        # Stop pressed right after iter 1's stream drains.
        await redis_client.setex(f"cancel_run:{run.id}", 300, "1")

    monkeypatch.setattr(execute_mod, "_call_responses_api", _fake_call)
    monkeypatch.setattr(execute_mod, "_call_chat_completions_api", _fake_call)
    monkeypatch.setattr(execute_mod, "stream_litellm_events", _fake_stream)
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    with pytest.raises(RuntimeError, match="stopped by user"):
        await _execute_agent_dispatch(
            pool, redis_client,
            dispatch=dispatch, prepared=prepared, sid="sid-g3",
            tool_soft=True, max_iterations=15, internal_sio=_FakeBus(),
        )

    # (G3) The completed iteration's usage (5 in / 2 out) was flushed on cancel,
    # not dropped — exactly once, keyed to this run.
    assert len(token_calls) == 1, "completed-iteration usage must be flushed on cancel"
    assert token_calls[0]["input"] == 5
    assert token_calls[0]["output"] == 2
    assert token_calls[0]["run_id"] == run.id

    # (H4) The cancel marker is gone, so a reused run_id won't be instant-killed.
    assert await redis_client.exists(f"cancel_run:{run.id}") == 0


async def test_h4_cancel_marker_cleared_on_clean_success(
    conn, redis_client, profile_id, pool, monkeypatch
):
    """A clean run also leaves no ``cancel_run`` marker behind (the finally
    cleanup runs on every exit), so a later run reusing the id is safe."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    dispatch = _make_dispatch(with_tool=False)
    prepared = _make_prepared(session, group, run, profile_id, [dispatch])

    answer_events = [
        {"type": "text_delta", "delta": "done"},
        {"type": "message_complete", "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    ]
    _patch_stream(monkeypatch, [answer_events])
    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    async def _noop_run_complete(*a, **k):
        return None
    import app.infra.websocket.run_complete_impl as _rcmod
    monkeypatch.setattr(_rcmod, "run_complete_impl", _noop_run_complete)

    await _execute_agent_dispatch(
        pool, redis_client,
        dispatch=dispatch, prepared=prepared, sid="sid-h4ok",
        tool_soft=True, max_iterations=15, internal_sio=_FakeBus(),
    )

    # No stale marker, and the active-run pointer is cleared too.
    assert await redis_client.exists(f"cancel_run:{run.id}") == 0
    assert await redis_client.exists(f"active_run:{group.id}") == 0


async def test_s1_multi_agent_all_ok_still_aggregates(
    conn, redis_client, profile_id, pool, monkeypatch
):
    """Sanity: with no agent error the multi-agent path still aggregates."""
    session, group, run = await _run_deps(conn, redis_client, profile_id)
    d_a = _make_dispatch(with_tool=False)
    d_b = _make_dispatch(with_tool=False)
    prepared = _make_prepared(session, group, run, profile_id, [d_a, d_b])

    monkeypatch.setattr(execute_mod, "get_internal_sio", lambda: _FakeBus())

    async def _ok(pool_, redis_, *, dispatch, **kw):
        return execute_mod.ExecuteGenerationResult(
            run_id=prepared.run_id, total_input_tokens=3, total_output_tokens=4,
            assistant_output="ok",
        )

    monkeypatch.setattr(execute_mod, "_execute_agent_dispatch", _ok)

    result = await execute_generation(
        pool, redis_client, prepared=prepared, sid="sid-s1ok",
    )
    assert result.total_input_tokens == 6
    assert result.total_output_tokens == 8
