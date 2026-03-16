"""End-to-end tests for the canonical group HTTP routes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import RouteActor, create_admin_route_actor


@dataclass(frozen=True)
class GroupRouteGraph:
    group_id: UUID
    run_id: UUID
    message_id: UUID
    call_id: UUID
    tool_id: UUID
    session_id: UUID


async def _create_group_route_graph(
    pool,
    redis_client,
    actor: RouteActor,
) -> GroupRouteGraph:
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.groups.create import create_group
    from app.tools.entries.messages.create import create_message
    from app.tools.entries.runs.create import create_run
    from app.tools.resources.agents.create import create_agent
    from app.tools.resources.models.create import create_model
    from app.tools.resources.tools.create import create_tool

    tag = unique_tag()

    async with pool.acquire() as conn:
        model = await create_model(
            conn,
            value=f"group-model-{tag}",
            name=f"Group Model {tag}",
            description=f"group model {tag}",
            redis=redis_client,
        )
        tool = await create_tool(
            conn,
            name=f"group-tool-{tag}",
            description=f"group tool {tag}",
            redis=redis_client,
        )
        agent = await create_agent(
            conn,
            name=f"Group Agent {tag}",
            description=f"group agent {tag}",
            redis=redis_client,
            model_id=model.id,
            tool_ids=[tool.id],
        )
        group = await create_group(
            conn,
            session_id=actor.session_id,
            name=f"group-route-{tag}",
        )
        run = await create_run(
            conn,
            group_id=group.id,
            session_id=actor.session_id,
            profiles_id=actor.profiles_id,
            agent_ids=[agent.id],
        )
        message = await create_message(conn, run_id=run.id, role="user")
        call = await create_call(
            conn,
            run_id=run.id,
            session_id=actor.session_id,
            external_call_id=f"call-{tag}",
            tool_id=tool.id,
        )
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY groups_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY runs_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY messages_mv")
        await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY calls_mv")

    return GroupRouteGraph(
        group_id=group.id,
        run_id=run.id,
        message_id=message.id,
        call_id=call.id,
        tool_id=tool.id,
        session_id=actor.session_id,
    )


@pytest_asyncio.fixture
async def group_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["group", "agent", "tool"],
        group_name="group-route-actor",
        role_name_prefix="Group Route Admin",
    )


@pytest.mark.asyncio
class TestGroupRoute:
    async def test_get_group_route_returns_group_detail(
        self,
        pool,
        redis_client,
        v5_group_route_client,
        group_route_actor,
    ):
        graph = await _create_group_route_graph(pool, redis_client, group_route_actor)
        v5_group_route_client.authenticate(
            profile_id=group_route_actor.profile_id,
            session_id=group_route_actor.session_id,
        )

        response = await v5_group_route_client.client.post(
            "/v5/group/get",
            json={"group_id": str(graph.group_id)},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,group,detail"
        assert response.headers["X-Cache-Hit"] == "0"

        payload = response.json()
        assert payload["group_exists"] is True
        assert payload["runs"]
        assert payload["runs"][0]["run"]["id"] == str(graph.run_id)
        assert payload["runs"][0]["messages"]
        assert payload["runs"][0]["messages"][0]["id"] == str(graph.message_id)

    async def test_get_group_route_caches_response(
        self,
        pool,
        redis_client,
        v5_group_route_client,
        group_route_actor,
    ):
        graph = await _create_group_route_graph(pool, redis_client, group_route_actor)
        v5_group_route_client.authenticate(
            profile_id=group_route_actor.profile_id,
            session_id=group_route_actor.session_id,
        )

        first = await v5_group_route_client.client.post(
            "/v5/group/get",
            json={"group_id": str(graph.group_id)},
        )
        second = await v5_group_route_client.client.post(
            "/v5/group/get",
            json={"group_id": str(graph.group_id)},
        )

        assert first.status_code == 200, first.text
        assert second.status_code == 200, second.text
        assert first.headers["X-Cache-Hit"] == "0"
        assert second.headers["X-Cache-Hit"] == "1"

    async def test_export_group_route_returns_upload(
        self,
        pool,
        redis_client,
        v5_group_route_client,
        group_route_actor,
    ):
        graph = await _create_group_route_graph(pool, redis_client, group_route_actor)
        v5_group_route_client.authenticate(
            profile_id=group_route_actor.profile_id,
            session_id=group_route_actor.session_id,
        )

        response = await v5_group_route_client.client.post(
            "/v5/group/export",
            json={"group_id": str(graph.group_id)},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".zip")
        assert payload["row_count"] >= 2
