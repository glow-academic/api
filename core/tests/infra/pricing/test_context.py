"""Integration tests for ``resolve_pricing_context`` / search context.

Exercises the pricing CONTEXT resolvers only — that a seeded pricing graph
(group + runs + run_pricing entries) surfaces in the resolved chart context
(runs with inline pricing counts + hydrated agent/model/pricing resources)
and the paginated search context (group history + runs for a session scope).
"""

from __future__ import annotations

import pytest

from app.infra.pricing.context import (
    resolve_pricing_context,
    resolve_pricing_search_context,
)
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.run_pricing.create import (
    create_run_pricing_entry_internal,
)
from app.tools.entries.runs.create import create_run
from app.tools.entries.sessions.create import create_session
from app.tools.resources.agents.create import create_agent
from app.tools.resources.models.create import create_model
from app.tools.resources.pricing.create import create_pricing

pytestmark = pytest.mark.asyncio


async def _seed_pricing_graph(conn, redis_client, profile_resource_id):
    session = await create_session(conn, redis_client, profile_id=profile_resource_id)
    group = await create_group(conn, redis_client, session_id=session.id, artifact_type="persona")
    await create_group_name(conn, redis_client, group.id, "Pricing Group", session.id)
    model = await create_model(
        conn,
        value="gpt-test-pricing",
        name="Pricing Model",
        redis=redis_client,
    )
    agent = await create_agent(
        conn,
        name="Pricing Agent",
        redis=redis_client,
        model_id=model.id,
    )
    input_pricing = await create_pricing(
        conn,
        "input",
        0.02,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    output_pricing = await create_pricing(
        conn,
        "output",
        0.03,
        "tokens",
        "tokens",
        1000,
        redis_client,
    )
    run = await create_run(
        conn,
        redis_client, group_id=group.id,
        session_id=session.id,
        agent_ids=[agent.id],
    )
    await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="input",
        run_id=run.id,
        pricing_id=input_pricing.id,
        count=1500,
    )
    await create_run_pricing_entry_internal(
        conn,
        redis_client, session_id=session.id,
        pricing_type="output",
        run_id=run.id,
        pricing_id=output_pricing.id,
        count=2000,
    )
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY group_names_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv")
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")
    return session, group, run, model, agent


class TestResolvePricingContext:
    async def test_returns_runs_and_hydrated_resources(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            _session, _group, run, model, agent = await _seed_pricing_graph(
                conn, redis_client, profile.profile_resource_id
            )

        result = await resolve_pricing_context(pool, redis_client)

        seeded_run = next(
            item for item in result.entries["runs"] if item.run_id == run.id
        )

        assert result.artifact_id is None
        assert seeded_run.run_id == run.id
        assert {item.count for item in seeded_run.pricing} == {1500, 2000}
        assert agent.id in [item.id for item in result.resources["agents"].selected]
        assert model.id in [item.id for item in result.resources["models"].selected]
        pricing_ids = {
            item.id for item in result.resources["pricing"].selected if item.id
        }
        assert len(pricing_ids) >= 2


class TestResolvePricingSearchContext:
    async def test_returns_group_history_with_runs(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            session, group, run, _model, _agent = await _seed_pricing_graph(
                conn, redis_client, profile.profile_resource_id
            )

        result = await resolve_pricing_search_context(
            pool,
            redis_client,
            session_ids=[session.id],
            page=0,
            page_size=10,
        )

        assert any(item.id == group.id for item in result.entries["groups"])
        assert any(item.id == group.id for item in result.entries["total_groups"])
        assert any(item.run_id == run.id for item in result.entries["runs"])
        assert "names" in result.resources
