"""S-C: prepare_generation pre-execute scaffold atomicity.

prepare.py used to write the run row, the eval scaffold
(setup_generation_test), and the per-agent framing messages across THREE
separate ``pool.acquire()`` calls — a failure mid-scaffold left a committed
active run with only part of its framing (and possibly a partial test). These
tests drive ``prepare_generation`` against a real agent graph (resolution +
scoring + agent-config resolution are stubbed so the test isolates the
scaffold-write block) and assert:

  * happy path — run + test + framing messages all land, and
  * a failure mid-scaffold (in ``persist_run_message``) leaves NO orphan
    run / test / messages: the whole scaffold rolls back atomically.

The scaffold writes are DB-only (no LLM/network call sits between them), so
prepare.py groups them into ONE transaction; the group-history reads are
pulled out into a separate pass. See prepare.py Step 9 / Step 10.
"""

from __future__ import annotations

from uuid import UUID

import pytest

import app.infra.generation.prepare as prepare_mod
from app.infra.generation.prepare import prepare_generation
from app.infra.types import WebsocketContext
from app.infra.websocket.generation_types import GeneratePayload
from app.infra.websocket.prepare_types import LLMConfig
from app.registry.generate import REGISTRY
from app.tools.entries.groups.create import create_group
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.get import get_agents

pytestmark = pytest.mark.asyncio


async def _runs_in_group(pool, redis_client, group_id: UUID) -> int:
    """Count committed run rows in a group, straight from the base table."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "SELECT count(*) FROM runs_entry WHERE group_id = $1", group_id
        )


async def _messages_in_group(pool, group_id: UUID) -> int:
    """Count messages whose run belongs to this group (messages_entry has no
    session_id; it links to a run, the run links to a group)."""
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            SELECT count(*)
            FROM messages_entry m
            JOIN runs_entry r ON r.id = m.run_id
            WHERE r.group_id = $1
            """,
            group_id,
        )


async def _tests_total(pool) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT count(*) FROM test_entry")


async def _wire_pipeline(monkeypatch, pool, redis_client, graph):
    """Stub resolution/scoring/agent-config so the call reaches the scaffold.

    Returns (session_id, group_id, agent). The agent is the REAL one from the
    system graph (it carries a rubric, so the eval-scaffold path fires).
    """
    from app.infra.tool_graph import ResolvedAgent, SettingsToolGraph

    async with pool.acquire() as conn:
        session = await create_session(conn, redis_client)
        group = await create_group(
            conn, redis_client, session_id=session.id, artifact_type="persona"
        )
        agents = await get_agents(conn, [graph.agent_id], redis_client, bypass_cache=True)
    agent = agents[0]

    resolved_agent = ResolvedAgent(
        agent_id=agent.id,
        system_id=graph.system_id,
        model_id=agent.model_id,
        input_modalities=frozenset({"text"}),
        output_modalities=frozenset({"text"}),
        tool_targets=frozenset(),
    )
    tool_graph = SettingsToolGraph(tools=[], agents=[resolved_agent])

    ws_ctx = WebsocketContext(
        scores=None,
        agents=[agent],
        models=[],
        providers=[],
        tools=[],
        args=[],
        args_outputs=[],
        permissions=[],
        prompts=[],
        instructions=[],
        tool_instructions=[],
        rubrics=[],
        profile=None,
        tool_graph=tool_graph,
    )

    async def fake_resolve_ws(*args, **kwargs):
        return ws_ctx

    def fake_score_agents(*args, **kwargs):
        return [resolved_agent]

    def fake_resolve_agent_config(*args, **kwargs):
        return LLMConfig(
            model="stub-model",
            api_key="stub-key",
            base_url="",
            temperature=0.0,
            reasoning=None,
            provider="stub",
            voice=None,
            quality=None,
        )

    # resolve_websocket_context + persist_run_message are module-level imports
    # in prepare.py → patch on prepare_mod. score_agents / resolve_agent_config
    # are imported LOCALLY inside prepare_generation, so they must be patched at
    # their source modules (the local ``from … import`` rebinds the name each call).
    import app.infra.tool_graph as tool_graph_mod
    import app.infra.websocket.prepare_pipeline as pipeline_mod

    monkeypatch.setattr(prepare_mod, "resolve_websocket_context", fake_resolve_ws)
    monkeypatch.setattr(tool_graph_mod, "score_agents", fake_score_agents)
    monkeypatch.setattr(pipeline_mod, "resolve_agent_config", fake_resolve_agent_config)

    return session.id, group.id, agent


async def _call_prepare(pool, redis_client, *, profile_id, session_id, group_id):
    config = REGISTRY.get("persona")
    payload = GeneratePayload(
        artifact_type="persona",
        instructions=["Make a persona."],
        operations=[],
    )
    return await prepare_generation(
        pool,
        redis_client,
        profile_id=profile_id,
        profiles_id=profile_id,
        session_id=session_id,
        group_id=group_id,
        artifact_type="persona",
        artifact_config=config,
        payload=payload,
    )


class TestPrepareScaffoldAtomicity:
    async def test_happy_path_writes_run_test_and_messages(
        self, pool, redis_client, system_graph_factory, monkeypatch
    ):
        graph = await system_graph_factory()
        session_id, group_id, agent = await _wire_pipeline(
            monkeypatch, pool, redis_client, graph
        )

        async with pool.acquire() as conn:
            from app.tools.resources.profiles.create import create_profile

            profile = await create_profile(conn, redis_client)

        result = await _call_prepare(
            pool, redis_client,
            profile_id=profile.id, session_id=session_id, group_id=group_id,
        )

        # Run committed, eval scaffold built (agent carries a rubric), and at
        # least the system-prompt framing message persisted.
        assert await _runs_in_group(pool, redis_client, group_id) == 1
        assert result.test_id is not None
        assert result.eval_setup is not None
        assert await _messages_in_group(pool, group_id) >= 1

        # The committed run row is the one prepare returned.
        async with pool.acquire() as conn:
            committed_run_id = await conn.fetchval(
                "SELECT id FROM runs_entry WHERE group_id = $1", group_id
            )
        assert committed_run_id == result.run_id

    async def test_failure_mid_scaffold_rolls_back_run_test_and_messages(
        self, pool, redis_client, system_graph_factory, monkeypatch
    ):
        graph = await system_graph_factory()
        session_id, group_id, agent = await _wire_pipeline(
            monkeypatch, pool, redis_client, graph
        )

        async with pool.acquire() as conn:
            from app.tools.resources.profiles.create import create_profile

            profile = await create_profile(conn, redis_client)

        tests_before = await _tests_total(pool)

        # Fail the message-persist step — it runs AFTER create_run +
        # setup_generation_test inside the same transaction. Without the
        # transaction the run row + the eval scaffold would already have
        # committed as orphans; with it, the whole scaffold rolls back.
        async def boom(*args, **kwargs):
            raise RuntimeError("injected mid-scaffold failure (persist message)")

        monkeypatch.setattr(prepare_mod, "persist_run_message", boom)

        with pytest.raises(RuntimeError, match="injected mid-scaffold failure"):
            await _call_prepare(
                pool, redis_client,
                profile_id=profile.id, session_id=session_id, group_id=group_id,
            )

        # Nothing from the scaffold survived: no run, no test, no messages.
        assert await _runs_in_group(pool, redis_client, group_id) == 0
        assert await _messages_in_group(pool, group_id) == 0
        assert await _tests_total(pool) == tests_before
