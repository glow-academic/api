"""Transcript reasoning visibility — H1 student vs instructor split.

Real DB + filesystem; deps injected (pool/redis/tmp_path).

Exercises ``_load_history`` directly (the function that builds the
runs→messages transcript both the instructor analytics view and the
student attempt transcript share). ``include_reasoning`` gates whether
chain-of-thought rows (``messages_entry.reasoning = true``) are surfaced:

  * instructor / analytics (default True) → reasoning row kept (collapsed
    "Thought for Xs" accordion);
  * student attempt transcript (False, wired in ``group_attempt_impl``) →
    reasoning row dropped, so the model's private CoT never leaks into the
    student's view of their own attempt.

Seeds + reads on pooled connections (committed) because ``_load_history``
opens its own pool connections.
"""

import pytest

from app.infra.group.resolve import _load_history
from app.infra.websocket.persist_run_message import persist_run_message
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _align_upload_folder(monkeypatch, tmp_path):
    import app.infra.globals as g
    monkeypatch.setattr(g, "UPLOAD_FOLDER", tmp_path)


async def _seed_reasoning_turn(pool, redis_client, tmp_path):
    async with pool.acquire() as c:
        profile_id = (await create_profile(c, redis_client)).id
        session = await create_session(c, redis_client, profile_id=profile_id)
        group = await create_group(
            c, redis_client, session_id=session.id, artifact_type="attempt"
        )
        run = await create_run(
            c, redis_client, group_id=group.id, session_id=session.id,
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="user", content="hello", upload_folder=tmp_path,
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="COT-PRIVATE-TRACE",
            upload_folder=tmp_path, reasoning=True,
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="visible answer", upload_folder=tmp_path,
        )
        await c.execute("REFRESH MATERIALIZED VIEW messages_mv")
        await c.execute("REFRESH MATERIALIZED VIEW runs_mv")
    return group


def _flat(runs_data):
    return [m for r in runs_data for m in r.messages]


async def test_instructor_view_keeps_reasoning(pool, redis_client, tmp_path):
    """Default include_reasoning=True surfaces the reasoning row (analytics)."""
    group = await _seed_reasoning_turn(pool, redis_client, tmp_path)
    runs_data, _ = await _load_history(pool, redis_client, group.id)
    msgs = _flat(runs_data)
    assert any(m.reasoning for m in msgs), "instructor view must keep reasoning row"
    # The answer + user turn are present too.
    assert any(m.role == "user" for m in msgs)


async def test_group_attempt_impl_defaults_reasoning_off(monkeypatch):
    """Wiring: the student attempt-group entry point passes include_reasoning=False
    to the shared resolver by default (instructor callers can still override)."""
    import app.infra.attempt.group as ag

    captured = {}

    class _FakeResult:
        def model_dump(self):
            return {"group_id": "00000000-0000-0000-0000-000000000000"}

    async def _fake_resolve(pool, redis, **kwargs):
        captured.update(kwargs)
        return _FakeResult()

    monkeypatch.setattr(ag, "resolve_group_impl", _fake_resolve)
    monkeypatch.setattr(
        ag.GroupAttemptApiResponse, "model_validate",
        classmethod(lambda cls, _d: object()),
    )
    await ag.group_attempt_impl(object(), object(), profile_id="p", session_id="s")
    assert captured.get("include_reasoning") is False

    captured.clear()
    await ag.group_attempt_impl(
        object(), object(), profile_id="p", session_id="s", include_reasoning=True,
    )
    assert captured.get("include_reasoning") is True


async def test_student_attempt_transcript_excludes_reasoning(
    pool, redis_client, tmp_path
):
    """Student attempt transcript drops the reasoning row entirely (H1)."""
    group = await _seed_reasoning_turn(pool, redis_client, tmp_path)
    runs_data, _ = await _load_history(
        pool, redis_client, group.id, include_reasoning=False
    )
    msgs = _flat(runs_data)
    assert msgs, "transcript should still contain the answer + user turns"
    assert all(not m.reasoning for m in msgs), "no reasoning rows in student view"
    # The non-reasoning assistant answer + the user turn survive.
    assert any(m.role == "assistant" for m in msgs)
    assert any(m.role == "user" for m in msgs)
