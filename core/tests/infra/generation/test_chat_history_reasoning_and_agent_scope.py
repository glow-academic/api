"""chat_history context assembly — H1 (reasoning out of context) + H2 (per-agent scope).

Real DB + filesystem; deps injected (pool/redis/tmp_path as params).

``fetch_group_history`` reads through ``pool``, so these tests seed + refresh +
read all on the SAME pooled connection (committed writes) — the rollback-only
``conn`` fixture's rows are invisible to a separate pool connection, and a
``REFRESH`` inside that open transaction would lock out the pool reader.

H1: ``fetch_group_history`` must NOT thread chain-of-thought rows
    (``messages_entry.reasoning = true``) back into the next turn's context.

H2: in a multi-agent run (ONE run, ``agent_ids=[A,B]``), each agent's assembled
    history must contain its OWN assistant turns + the shared user turns, but NOT
    the OTHER agent's assistant turns.
"""

import pytest

from app.infra.generation.chat_history import fetch_group_history
from app.infra.websocket.persist_run_message import persist_run_message
from app.tools.entries.groups.create import create_group
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent
from app.tools.resources.profiles.create import create_profile

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _align_upload_folder(monkeypatch, tmp_path):
    """chat_history binds ``UPLOAD_FOLDER`` at import; align it (and the
    persist default) to ``tmp_path`` so the message text the test writes is
    the same text ``fetch_group_history`` reads back."""
    import app.infra.generation.chat_history as ch
    import app.infra.globals as g

    monkeypatch.setattr(ch, "UPLOAD_FOLDER", tmp_path)
    monkeypatch.setattr(g, "UPLOAD_FOLDER", tmp_path)


async def _refresh(c):
    await c.execute("REFRESH MATERIALIZED VIEW messages_mv")
    await c.execute("REFRESH MATERIALIZED VIEW runs_mv")


async def test_reasoning_excluded_from_next_turn_context(
    pool, redis_client, tmp_path
):
    """H1: a reasoning=True row never appears as assistant content in history."""
    async with pool.acquire() as c:
        profile_id = (await create_profile(c, redis_client)).id
        session = await create_session(c, redis_client, profile_id=profile_id)
        group = await create_group(
            c, redis_client, session_id=session.id, artifact_type="attempt"
        )
        agent = await create_agent(c, name="h1-agent", redis=redis_client)
        run = await create_run(
            c, redis_client, group_id=group.id, session_id=session.id,
            agent_ids=[agent.id],
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="user", content="solve 2+2", upload_folder=tmp_path,
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="SECRET-COT let me think step by step",
            upload_folder=tmp_path, reasoning=True, agent_ids=[agent.id],
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="The answer is 4.",
            upload_folder=tmp_path, agent_ids=[agent.id],
        )
        await _refresh(c)

    history = await fetch_group_history(pool, group_id=group.id, agent_id=agent.id)
    texts = [h.text for h in history]
    assert any("The answer is 4." in t for t in texts), "answer must be threaded"
    assert all("SECRET-COT" not in t for t in texts), "reasoning must NOT be threaded"


async def test_multi_agent_history_scoped_to_own_agent(
    pool, redis_client, tmp_path
):
    """H2: agent B's history has B's answer + the shared user turn, NOT A's answer."""
    async with pool.acquire() as c:
        profile_id = (await create_profile(c, redis_client)).id
        session = await create_session(c, redis_client, profile_id=profile_id)
        group = await create_group(
            c, redis_client, session_id=session.id, artifact_type="persona"
        )
        agent_a = await create_agent(c, name="agent-a", redis=redis_client)
        agent_b = await create_agent(c, name="agent-b", redis=redis_client)
        run = await create_run(
            c, redis_client, group_id=group.id, session_id=session.id,
            agent_ids=[agent_a.id, agent_b.id],
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="user", content="SHARED-USER-PROMPT", upload_folder=tmp_path,
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="ANSWER-FROM-A",
            upload_folder=tmp_path, agent_ids=[agent_a.id],
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="ANSWER-FROM-B",
            upload_folder=tmp_path, agent_ids=[agent_b.id],
        )
        await _refresh(c)

    hist_b = await fetch_group_history(pool, group_id=group.id, agent_id=agent_b.id)
    texts_b = [h.text for h in hist_b]
    assert any("SHARED-USER-PROMPT" in t for t in texts_b), "shared user turn kept"
    assert any("ANSWER-FROM-B" in t for t in texts_b), "own answer kept"
    assert all("ANSWER-FROM-A" not in t for t in texts_b), "other agent's answer dropped"

    hist_a = await fetch_group_history(pool, group_id=group.id, agent_id=agent_a.id)
    texts_a = [h.text for h in hist_a]
    assert any("SHARED-USER-PROMPT" in t for t in texts_a)
    assert any("ANSWER-FROM-A" in t for t in texts_a)
    assert all("ANSWER-FROM-B" not in t for t in texts_a)


async def test_unattributed_assistant_rows_are_shared(
    pool, redis_client, tmp_path
):
    """H2 backward-compat: assistant rows with NO agent link stay visible to all."""
    async with pool.acquire() as c:
        profile_id = (await create_profile(c, redis_client)).id
        session = await create_session(c, redis_client, profile_id=profile_id)
        group = await create_group(
            c, redis_client, session_id=session.id, artifact_type="persona"
        )
        agent_a = await create_agent(c, name="bc-agent-a", redis=redis_client)
        agent_b = await create_agent(c, name="bc-agent-b", redis=redis_client)
        run = await create_run(
            c, redis_client, group_id=group.id, session_id=session.id,
            agent_ids=[agent_a.id, agent_b.id],
        )
        await persist_run_message(
            c, redis_client, run_id=run.id, session_id=session.id,
            role="assistant", content="LEGACY-UNATTRIBUTED", upload_folder=tmp_path,
        )
        await _refresh(c)

    hist_b = await fetch_group_history(pool, group_id=group.id, agent_id=agent_b.id)
    assert any("LEGACY-UNATTRIBUTED" in h.text for h in hist_b)
