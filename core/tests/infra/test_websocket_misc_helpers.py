"""Tests for small websocket helper utilities."""

import pytest
from fastapi import APIRouter
from pydantic import BaseModel

import app.infra.globals as globals_mod
from app.infra.websocket.get_db_connection import get_db_connection
from app.infra.websocket.is_run_cancelled import is_run_cancelled
from app.infra.websocket.openapi_helpers import (
    _generate_unique_function_name,
    register_client_endpoint,
    register_server_endpoint,
)


class ExamplePayload(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_is_run_cancelled_uses_real_redis(redis_client):
    original_redis = globals_mod.redis_client
    try:
        globals_mod.redis_client = redis_client
        assert await is_run_cancelled("run-1") is False

        await redis_client.set("cancel_run:run-1", "1")

        assert await is_run_cancelled("run-1") is True
    finally:
        globals_mod.redis_client = original_redis


@pytest.mark.asyncio
async def test_get_db_connection_yields_connection_from_pool(pool):
    original_pool = globals_mod._db_pool
    try:
        globals_mod._db_pool = pool
        async with get_db_connection() as conn:
            value = await conn.fetchval("SELECT 1")
        assert value == 1
    finally:
        globals_mod._db_pool = original_pool


@pytest.mark.asyncio
async def test_get_db_connection_raises_without_pool():
    original_pool = globals_mod._db_pool
    try:
        globals_mod._db_pool = None
        with pytest.raises(
            RuntimeError, match="Database connection pool not initialized"
        ):
            async with get_db_connection():
                pass
    finally:
        globals_mod._db_pool = original_pool


def test_generate_unique_function_name_uses_router_prefix_and_path():
    router = APIRouter(prefix="/socket/v5/chat")

    name = _generate_unique_function_name(router, "/generate")

    assert name.startswith("handle_")
    assert "socket_v5_chat" in name
    assert name.endswith("generate")


def test_register_endpoint_helpers_add_routes_with_operation_ids():
    router = APIRouter(prefix="/socket/v5/test")

    register_client_endpoint(router, "/client", ExamplePayload, "Client event")
    register_server_endpoint(router, "/server", ExamplePayload, "Server event")

    paths = {route.path: route for route in router.routes}
    assert "/socket/v5/test/client" in paths
    assert "/socket/v5/test/server" in paths
    assert paths["/socket/v5/test/client"].operation_id is not None
    assert paths["/socket/v5/test/server"].operation_id is not None
