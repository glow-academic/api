"""Tests for introspection-based MCP tool registration."""

from __future__ import annotations

from uuid import uuid4

import pytest
import pytest_asyncio

from app.infra.mcp.register import (
    _build_tool_args,
    _get_request_model,
    _import_handler,
    register_tools,
)
from app.infra.mcp.tool_graph import get_mcp_tool_graph
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def mcp_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["persona"],
        group_name="mcp-endpoints",
        role_name_prefix="MCP Endpoint Admin",
    )


def test_tool_graph_returns_non_empty_list():
    graph = get_mcp_tool_graph()

    assert len(graph) > 20
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in graph)
    assert ("persona", "get") in graph
    assert ("scenario", "search") in graph


def test_import_handler_finds_router_endpoint():
    handler = _import_handler("app.routes.v5.persona.get")

    assert callable(handler)
    assert handler.__name__ != "_"


def test_import_handler_raises_for_unknown_module():
    with pytest.raises(ModuleNotFoundError):
        _import_handler("app.routes.v5.not_real.missing")


def test_get_request_model_extracts_pydantic_model():
    handler = _import_handler("app.routes.v5.persona.get")
    model = _get_request_model(handler)

    assert model is not None
    assert hasattr(model, "model_json_schema")


def test_build_tool_args_excludes_mcp_field():
    handler = _import_handler("app.routes.v5.persona.get")
    model = _get_request_model(handler)
    assert model is not None

    args = _build_tool_args(model)

    arg_names = [a["name"] for a in args]
    assert "mcp" not in arg_names
    assert "persona_id" in arg_names


def test_register_tools_registers_all_graph_entries():
    """All graph entries get registered — failures are deferred to call time."""

    class FakeServer:
        def __init__(self):
            self.tools: dict[str, object] = {}

        def tool(self):
            def _decorator(fn):
                self.tools[fn.__name__] = fn
                return fn

            return _decorator

    server = FakeServer()
    graph = get_mcp_tool_graph()

    register_tools(server, graph)

    assert len(server.tools) == len(graph)
    assert "get_persona" in server.tools
    assert "search_scenario" in server.tools
    assert "draft_simulation" in server.tools


@pytest.mark.asyncio
async def test_call_handler_executes_real_persona_get(
    pool,
    redis_client,
    mcp_actor,
):
    import app.infra.globals as globals_mod
    from app.infra.mcp.register import _call_handler, _resolve_handler_and_model

    handler, model = _resolve_handler_and_model("app.routes.v5.persona.get")

    # Create a persona to query
    from app.tools.artifacts.persona.create import create_persona
    from app.tools.resources.names.create import create_name

    async with pool.acquire() as conn:
        name = await create_name(conn, f"mcp-persona-{uuid4()}", redis_client)
        persona = await create_persona(
            conn,
            name_id=name.id,
            department_ids=[mcp_actor.department_id],
        )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client
    try:
        result = await _call_handler(
            handler,
            model,
            {"persona_id": str(persona.id)},
            str(mcp_actor.profile_id),
        )
    finally:
        globals_mod._db_pool = prior_pool
        globals_mod.redis_client = prior_redis

    assert "error" not in result
    assert result["persona_exists"] is True
