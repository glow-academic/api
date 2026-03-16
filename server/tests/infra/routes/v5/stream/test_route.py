"""Route tests for centralized SSE event streaming."""

from __future__ import annotations

import asyncio
from datetime import datetime, UTC
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from starlette.requests import Request as StarletteRequest
from tests.infra.route_helpers import create_admin_route_actor

from app.infra.stream.types import EventEnvelope
from app.infra.stream.emitter import emit_artifact_operation_events
from app.infra.stream.registry import get_artifact_events_config
from app.routes.stream import stream_events


@pytest_asyncio.fixture
async def events_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        tool_artifacts=["persona", "test", "session"],
        group_name="events-route",
        role_name_prefix="Events Route Admin",
    )


async def _create_persona_id(pool, redis_client, department_id: UUID) -> UUID:
    from app.tools.artifacts.persona.create import create_persona
    from app.tools.resources.names.create import create_name

    async with pool.acquire() as conn:
        name = await create_name(conn, f"stream-persona-{uuid4()}", redis_client)
        persona = await create_persona(
            conn,
            name_id=name.id,
            department_ids=[department_id],
        )
    return persona.id


async def _collect_stream_events(
    response,
    *,
    stop_event: str,
    max_chunks: int = 8,
) -> list[str]:
    events: list[str] = []
    iterator = response.body_iterator.__aiter__()
    for _ in range(max_chunks):
        chunk = await asyncio.wait_for(iterator.__anext__(), timeout=2)
        if isinstance(chunk, bytes):
            chunk = chunk.decode()
        for line in str(chunk).splitlines():
            if line.startswith("event: "):
                events.append(line.removeprefix("event: "))
                if events[-1] == stop_event:
                    return events
    return events


def _build_stream_request(profile_id: UUID, session_id: UUID) -> StarletteRequest:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v5/stream/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
    }
    request = StarletteRequest(scope)
    request.state.profile_id = str(profile_id)
    request.state.session_id = str(session_id)
    return request


@pytest.mark.asyncio
class TestEventsRoutes:
    async def test_stream_requires_entity_id_for_entity_scoped_operations(
        self,
        v5_events_route_client,
        events_route_actor,
    ):
        v5_events_route_client.authenticate(
            profile_id=events_route_actor.profile_id,
            session_id=events_route_actor.session_id,
        )

        response = await v5_events_route_client.client.get(
            "/v5/stream/",
            params={"artifact": "persona", "operation": "get"},
        )

        assert response.status_code == 400, response.text
        assert "entity_id is required" in response.json()["detail"]

    async def test_stream_requires_authentication(
        self,
        v5_events_route_client,
    ):
        response = await v5_events_route_client.client.get(
            "/v5/stream/",
            params={"artifact": "persona", "operation": "search", "limit": 5},
        )

        assert response.status_code == 401, response.text

    async def test_stream_emits_sse_lines_for_projected_events(
        self,
        monkeypatch,
        pool,
        redis_client,
        v5_events_route_client,
        events_route_actor,
    ):
        persona_id = await _create_persona_id(
            pool,
            redis_client,
            events_route_actor.department_id,
        )
        created_at = datetime.now(UTC)
        expected_events = [
            EventEnvelope(
                id=f"{uuid4()}:started",
                event_type="artifacts.persona.get.started",
                artifact="persona",
                operation="get",
                created_at=created_at,
                entity_id=persona_id,
                call_id=uuid4(),
                tool_id=uuid4(),
                payload={"arguments": {"persona_id": str(persona_id)}},
            ),
            EventEnvelope(
                id=f"{uuid4()}:completed",
                event_type="artifacts.persona.get.completed",
                artifact="persona",
                operation="get",
                created_at=created_at,
                entity_id=persona_id,
                call_id=uuid4(),
                tool_id=uuid4(),
                payload={"output": {"ok": True}},
            ),
            EventEnvelope(
                id=f"{uuid4()}:viewed",
                event_type="artifacts.persona.viewed",
                artifact="persona",
                operation="get",
                created_at=created_at,
                entity_id=persona_id,
                call_id=uuid4(),
                tool_id=uuid4(),
                payload={},
            ),
        ]

        async def _read_artifact_events(*_args, **_kwargs):
            return expected_events

        monkeypatch.setattr(
            "app.routes.stream.read_artifact_events",
            _read_artifact_events,
        )

        request = _build_stream_request(
            events_route_actor.profile_id,
            events_route_actor.session_id,
        )
        response = await stream_events(
            request,
            artifact="persona",
            operation="get",
            entity_id=persona_id,
            cursor=None,
            types=None,
            limit=10,
        )
        events = await _collect_stream_events(
            response,
            stop_event="artifacts.persona.viewed",
        )

        assert events[:3] == [
            "artifacts.persona.get.started",
            "artifacts.persona.get.completed",
            "artifacts.persona.viewed",
        ]

    async def test_stream_filters_to_requested_event_types(
        self,
        monkeypatch,
        pool,
        redis_client,
        v5_events_route_client,
        events_route_actor,
    ):
        persona_id = await _create_persona_id(
            pool,
            redis_client,
            events_route_actor.department_id,
        )
        expected_events = [
            EventEnvelope(
                id=f"{uuid4()}:viewed",
                event_type="artifacts.persona.viewed",
                artifact="persona",
                operation="get",
                created_at=datetime.now(UTC),
                entity_id=persona_id,
                call_id=uuid4(),
                tool_id=uuid4(),
                payload={},
            )
        ]

        async def _read_artifact_events(*_args, **_kwargs):
            return expected_events

        monkeypatch.setattr(
            "app.routes.stream.read_artifact_events",
            _read_artifact_events,
        )

        request = _build_stream_request(
            events_route_actor.profile_id,
            events_route_actor.session_id,
        )
        response = await stream_events(
            request,
            artifact="persona",
            operation="get",
            entity_id=persona_id,
            cursor=None,
            types=["artifacts.persona.viewed"],
            limit=10,
        )
        events = await _collect_stream_events(
            response,
            stop_event="artifacts.persona.viewed",
            max_chunks=3,
        )

        assert events == ["artifacts.persona.viewed"]

    async def test_stream_emits_live_events_from_hub_when_store_is_empty(
        self,
        monkeypatch,
        events_route_actor,
    ):
        async def _read_artifact_events(*_args, **_kwargs):
            return []

        monkeypatch.setattr(
            "app.routes.stream.read_artifact_events",
            _read_artifact_events,
        )
        persona_config = get_artifact_events_config("persona")
        assert persona_config is not None
        operation_config = persona_config.get_operation("create")
        assert operation_config is not None
        async def _resolve_subscription(**_kwargs):
            return persona_config, operation_config
        monkeypatch.setattr(
            "app.routes.stream.resolve_subscription",
            _resolve_subscription,
        )

        request = _build_stream_request(
            events_route_actor.profile_id,
            events_route_actor.session_id,
        )
        response = await stream_events(
            request,
            artifact="persona",
            operation="create",
            entity_id=None,
            cursor=None,
            types=None,
            limit=10,
        )

        async def _emit():
            await asyncio.sleep(0.1)
            await emit_artifact_operation_events(
                artifact="persona",
                operation="create",
                arguments={"personas": [{"name": "Live Persona"}]},
                output={
                    "success": True,
                    "results": [
                        {
                            "success": True,
                            "persona_id": "019ce726-fa14-7f2a-aebb-0067bca4b029",
                            "message": "ok",
                        }
                    ],
                },
            )

        task = asyncio.create_task(_emit())
        try:
            events = await _collect_stream_events(
                response,
                stop_event="artifacts.persona.created",
                max_chunks=8,
            )
        finally:
            await task

        assert events == [
            "artifacts.persona.create.started",
            "artifacts.persona.create.completed",
            "artifacts.persona.created",
        ]
