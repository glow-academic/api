"""End-to-end tests for the canonical pricing HTTP routes."""

from __future__ import annotations


import pytest
import pytest_asyncio

from tests.infra.route_helpers import create_admin_route_actor


async def _seed_pricing_route_graph(pool, redis_client, actor):
    from app.infra.globals import UPLOAD_FOLDER
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

    async with pool.acquire() as conn:
        session = await create_session(
            conn, redis_client, profile_id=actor.profiles_id
        )
        group = await create_group(
            conn, redis_client, session_id=session.id, artifact_type="system"
        )
        await create_group_name(
            conn,
            redis_client,
            group_id=group.id,
            name="Pricing Route Group",
            session_id=session.id,
        )
        model = await create_model(
            conn,
            value="gpt-pricing-route",
            name="Pricing Route Model",
            description="Route test pricing model",
            redis=redis_client,
        )
        agent = await create_agent(
            conn,
            name="Pricing Route Agent",
            description="Route test pricing agent",
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
            redis_client,
            group_id=group.id,
            session_id=session.id,
            agent_ids=[agent.id],
        )
        await create_run_pricing_entry_internal(
            conn,
            redis_client,
            session_id=session.id,
            pricing_type="input",
            run_id=run.id,
            pricing_id=input_pricing.id,
            count=1500,
        )
        await create_run_pricing_entry_internal(
            conn,
            redis_client,
            session_id=session.id,
            pricing_type="output",
            run_id=run.id,
            pricing_id=output_pricing.id,
            count=2000,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY run_pricing_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")

    return {
        "session_id": str(session.id),
        "group_id": str(group.id),
        "run_id": str(run.id),
        "upload_folder": UPLOAD_FOLDER,
    }


@pytest_asyncio.fixture
async def pricing_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="pricing-route",
        role_name_prefix="Pricing Route Admin",
    )


@pytest.mark.asyncio
class TestPricingRoute:
    async def test_get_pricing_route_returns_aggregated_runs(
        self,
        pool,
        redis_client,
        pricing_route_client,
        pricing_route_actor,
    ):
        await _seed_pricing_route_graph(pool, redis_client, pricing_route_actor)
        pricing_route_client.authenticate(
            profile_id=pricing_route_actor.profile_id,
            session_id=pricing_route_actor.session_id,
        )

        response = await pricing_route_client.client.post(
            "/pricing",
            json={
                "history_page": 0,
                "history_page_size": 10,
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,pricing"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["total_count"] >= 1
        assert payload["daily"]
        assert payload["resources"]["agents"]
        assert payload["resources"]["models"]
        assert payload["analytics"] is not None
        # Paginated history is no longer inline on the pricing GET bundle
        # (PricingResponse.history is always null — fetch via /system/groups).
        assert payload["history"] is None

    # NOTE: removed test_search_pricing_route_returns_group_history,
    # test_pricing_docs_route_returns_composed_docs,
    # test_pricing_export_route_creates_zip_upload, and
    # test_pricing_refresh_route_returns_invalidated_tags — the pricing
    # search/docs/export/refresh operations were consolidated into the system
    # parent (`/system/groups`-style lists, `/system/context`, view-aware
    # `/system/export`, `/system/refresh`). The pricing artifact exposes only
    # the root `POST /pricing` bundle; there are no
    # `/pricing/{search,docs,export,refresh}` routes and the pricing route
    # client mounts only the root pricing module.
