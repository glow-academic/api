"""Focused tests for the top-level FastAPI app assembly."""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace

import pytest
import socketio  # type: ignore
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.server import (
    DBLoggingMiddleware,
    _build_voice_session_reaper,
    _configure_named_loggers,
    _initialize_redis_client,
    _write_openapi_schema,
    app,
    fastapi_app,
)


def test_fastapi_app_mounts_expected_top_level_routes_and_middleware():
    route_paths = {getattr(route, "path", None) for route in fastapi_app.routes}
    middleware_names = {
        middleware.cls.__name__ for middleware in fastapi_app.user_middleware
    }

    assert fastapi_app.title == "GLOW API"
    assert "/.well-known/oauth-authorization-server" in route_paths
    assert "DBLoggingMiddleware" in middleware_names
    assert "McpOAuthMiddleware" in middleware_names
    assert isinstance(app, socketio.ASGIApp)


def test_configure_named_loggers_sets_formatter_on_existing_and_new_handlers():
    logger_one = logging.getLogger("test.server.logger.one")
    logger_one.handlers = [logging.StreamHandler()]
    logger_two = logging.getLogger("test.server.logger.two")
    logger_two.handlers = []

    formatter = logging.Formatter("%(message)s")

    _configure_named_loggers(
        ["test.server.logger.one", "test.server.logger.two"],
        formatter,
    )

    assert logger_one.handlers[0].formatter is formatter
    assert logger_two.handlers
    assert logger_two.handlers[0].formatter is formatter


@pytest.mark.asyncio
async def test_initialize_redis_client_sets_none_when_missing_config():
    globals_module = SimpleNamespace(redis_client="sentinel")
    test_logger = logging.getLogger("test.server.redis.none")

    result = await _initialize_redis_client(
        redis_module=None,
        redis_url=None,
        globals_module=globals_module,
        logger_obj=test_logger,
    )

    assert result is None
    assert globals_module.redis_client is None


@pytest.mark.asyncio
async def test_initialize_redis_client_stores_live_client_on_success():
    class _FakeClient:
        def __init__(self) -> None:
            self.pinged = False

        async def ping(self) -> None:
            self.pinged = True

    class _FakeRedis:
        def __init__(self) -> None:
            self.client = _FakeClient()

        def from_url(self, url: str) -> _FakeClient:
            assert url == "redis://localhost:6379/0"
            return self.client

    globals_module = SimpleNamespace(redis_client=None)
    redis_module = _FakeRedis()

    result = await _initialize_redis_client(
        redis_module=redis_module,
        redis_url="redis://localhost:6379/0",
        globals_module=globals_module,
        logger_obj=logging.getLogger("test.server.redis.success"),
    )

    assert result is redis_module.client
    assert redis_module.client.pinged is True
    assert globals_module.redis_client is redis_module.client


def test_write_openapi_schema_adds_cache_tags_and_writes_json(tmp_path):
    openapi_path = tmp_path / "openapi.json"
    app = FastAPI(title="OpenAPI Test")
    app.get("/items", tags=["items"])(lambda: {"ok": True})

    path = _write_openapi_schema(app, output_path=openapi_path)

    payload = json.loads(path.read_text())
    assert payload["paths"]["/items"]["get"]["x-cache-tags"] == ["items"]
    assert path == openapi_path


@pytest.mark.asyncio
async def test_voice_session_reaper_cleans_up_stale_sessions_and_exits_on_cancel():
    cleaned_sessions: list[str] = []
    sleep_calls = 0

    async def cleanup_audio_session(session: object) -> None:
        cleaned_sessions.append(session.group_id)

    def get_stale_sessions(*, timeout: float) -> list[object]:
        assert timeout == 300.0
        return [SimpleNamespace(group_id="group-123")]

    async def sleep_once(_interval: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        if sleep_calls > 1:
            raise asyncio.CancelledError

    reaper = _build_voice_session_reaper(
        cleanup_audio_session_fn=cleanup_audio_session,
        get_stale_sessions_fn=get_stale_sessions,
        sleep_fn=sleep_once,
        logger_obj=logging.getLogger("test.server.reaper"),
    )

    await reaper()

    assert cleaned_sessions == ["group-123"]


@pytest.mark.asyncio
async def test_db_logging_middleware_records_profile_and_request_duration():
    recorded_profile_ids: list[str | None] = []
    request_durations: list[float] = []
    error_calls = 0

    async def record_request(duration_ms: float) -> None:
        request_durations.append(duration_ms)

    async def record_error() -> None:
        nonlocal error_calls
        error_calls += 1

    def set_profile_id(profile_id: str | None) -> None:
        recorded_profile_ids.append(profile_id)

    test_app = FastAPI()

    @test_app.post("/echo")
    async def echo(request: Request) -> dict[str, str]:
        request.state.profile_id = "state-profile-123"
        return {"ok": "yes"}

    test_app.add_middleware(
        DBLoggingMiddleware,
        record_error_fn=record_error,
        record_request_fn=record_request,
        set_profile_id_fn=set_profile_id,
    )

    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/echo", json={"profile_id": "body-profile-456"})

    await asyncio.sleep(0)

    assert response.status_code == 200
    assert error_calls == 0
    assert request_durations
    assert recorded_profile_ids[0] == "body-profile-456"
    assert recorded_profile_ids[-1] is None


@pytest.mark.asyncio
async def test_db_logging_middleware_records_errors_for_failing_requests():
    recorded_profile_ids: list[str | None] = []
    request_durations: list[float] = []
    error_calls = 0

    async def record_request(duration_ms: float) -> None:
        request_durations.append(duration_ms)

    async def record_error() -> None:
        nonlocal error_calls
        error_calls += 1

    def set_profile_id(profile_id: str | None) -> None:
        recorded_profile_ids.append(profile_id)

    test_app = FastAPI()

    @test_app.post("/boom")
    async def boom() -> None:
        raise RuntimeError("boom")

    test_app.add_middleware(
        DBLoggingMiddleware,
        record_error_fn=record_error,
        record_request_fn=record_request,
        set_profile_id_fn=set_profile_id,
    )

    async with AsyncClient(
        transport=ASGITransport(app=test_app, raise_app_exceptions=False),
        base_url="http://testserver",
    ) as client:
        response = await client.post("/boom", json={"profile_id": "body-profile-456"})

    await asyncio.sleep(0)

    assert response.status_code == 500
    assert error_calls == 1
    assert request_durations
    assert recorded_profile_ids[0] == "body-profile-456"
    assert recorded_profile_ids[-1] is None
