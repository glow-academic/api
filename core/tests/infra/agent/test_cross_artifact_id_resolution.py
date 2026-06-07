"""Regression: agent create/update resolves model/tool/rubric artifact IDs to resource IDs.

Clients (and ``/model/search`` / ``/tool/search`` / ``/rubric/search``) surface
*artifact* IDs, but the agent junctions reference the denormalized ``*_resource``
snapshot each of those artifacts owns via its own self-junction:

  - ``agent_models_junction.models_id``  -> ``models_resource``  (NO FK: silent mislink)
  - ``agent_tools_junction.tools_id``    -> ``tools_resource``   (FK: 500 on artifact id)
  - ``agent_rubrics_junction.rubrics_id``-> ``rubrics_resource`` (FK: 500 on artifact id)

Before the fix ``resolve_agent_values`` passed the artifact IDs straight through.
These mutation-verified tests exercise the real DB pool through black-box tools
only (no raw SQL): they seed each ``*_resource`` snapshot + a linked artifact,
then prove resolution rewrites the artifact ID to its resource ID.
"""

from uuid import uuid4

import pytest

from app.infra.agent.permissions_context import resolve_agent_values
from app.infra.agent.types import CreateAgentItem
from app.tools.artifacts.model.create import create_model as create_model_artifact
from app.tools.artifacts.rubric.create import create_rubric as create_rubric_artifact
from app.tools.artifacts.tool.create import create_tool as create_tool_artifact
from app.tools.resources.models.create import create_model as create_model_resource
from app.tools.resources.rubrics.create import create_rubric as create_rubric_resource
from app.tools.resources.tools.create import create_tool as create_tool_resource

pytestmark = pytest.mark.asyncio


async def _seed_model(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_model_resource(
            conn, value=f"m-{uuid4().hex[:8]}", name="agent-model", redis=redis_client
        )
        artifact = await create_model_artifact(conn, model_ids=[resource.id])
    return artifact.id, resource.id


async def _seed_tool(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_tool_resource(
            conn, name=f"t-{uuid4().hex[:8]}", redis=redis_client
        )
        artifact = await create_tool_artifact(conn, tool_ids=[resource.id])
    return artifact.id, resource.id


async def _seed_rubric(pool, redis_client) -> tuple:
    async with pool.acquire() as conn:
        resource = await create_rubric_resource(
            conn, redis_client, name=f"r-{uuid4().hex[:8]}"
        )
        artifact = await create_rubric_artifact(conn, rubric_ids=[resource.id])
    return artifact.id, resource.id


async def test_resolve_rewrites_model_tool_rubric_artifact_ids(pool, redis_client):
    model_a, model_r = await _seed_model(pool, redis_client)
    tool_a, tool_r = await _seed_tool(pool, redis_client)
    rubric_a, rubric_r = await _seed_rubric(pool, redis_client)

    item = CreateAgentItem(
        name="agent-xref",
        model_id=model_a,
        tool_ids=[tool_a],
        rubric_ids=[rubric_a],
    )
    async with pool.acquire() as conn:
        errors = await resolve_agent_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.model_id == model_r and item.model_id != model_a
    assert item.tool_ids == [tool_r] and tool_a not in item.tool_ids
    assert item.rubric_ids == [rubric_r] and rubric_a not in item.rubric_ids


async def test_unknown_cross_artifact_ids_pass_through(pool, redis_client):
    m, t, r = uuid4(), uuid4(), uuid4()
    item = CreateAgentItem(name="agent-xref-2", model_id=m, tool_ids=[t], rubric_ids=[r])
    async with pool.acquire() as conn:
        errors = await resolve_agent_values(conn, redis_client, item, is_create=True)

    assert errors == []
    assert item.model_id == m
    assert item.tool_ids == [t]
    assert item.rubric_ids == [r]
