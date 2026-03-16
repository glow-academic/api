"""End-to-end tests for the canonical health HTTP routes."""

from __future__ import annotations

import io
import base64
import zipfile
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


async def _seed_health_metrics(conn) -> None:
    from app.tools.entries.health.create import create_health
    from app.tools.entries.metrics.create import create_metrics_entry_internal
    from app.tools.entries.metrics.refresh import refresh_metrics_internal

    await create_health(
        conn,
        service="redis",
        ok=True,
        latency_ms=12.5,
        ts=datetime(2031, 1, 1, 10, 0, tzinfo=UTC),
    )
    await create_metrics_entry_internal(
        conn,
        ts=datetime(2031, 1, 1, 10, 0, tzinfo=UTC),
        requests_total=100,
        errors_total=2,
        avg_latency_ms=45.5,
        cpu_percent=33.3,
        memory_bytes=123456,
    )
    await conn.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY health_mv")
    await refresh_metrics_internal(conn)


@pytest_asyncio.fixture
async def health_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="health-route",
        role_name_prefix="Health Route Admin",
    )


@pytest.mark.asyncio
class TestHealthRoute:
    async def test_get_health_route_returns_health_views(
        self,
        pool,
        v5_health_route_client,
        health_route_actor,
    ):
        async with pool.acquire() as conn:
            await _seed_health_metrics(conn)

        v5_health_route_client.authenticate(
            profile_id=health_route_actor.profile_id,
            session_id=health_route_actor.session_id,
        )
        response = await v5_health_route_client.client.post(
            "/v5/health/get",
            json={
                "service": "redis",
                "date_from": "2031-01-01T00:00:00Z",
                "date_to": "2031-01-02T00:00:00Z",
                "page_limit": 24,
                "page_offset": 0,
            },
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,health"

        payload = response.json()
        assert payload["total_count"] >= 1
        assert payload["views"]["service_hourly"]
        assert payload["views"]["service_hourly"][0]["service"] == "redis"
        assert payload["views"]["metrics_hourly"]
        assert payload["analytics"] is not None

    async def test_health_docs_route_returns_composed_docs(
        self,
        v5_health_route_client,
        health_route_actor,
    ):
        v5_health_route_client.authenticate(
            profile_id=health_route_actor.profile_id,
            session_id=health_route_actor.session_id,
        )
        response = await v5_health_route_client.client.post(
            "/v5/health/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "health"
        assert payload["type"] == "analytics"
        assert payload["entries"]
        assert payload["page_metadata"]["list"]["title"] == "Health"
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {"get_health", "health_refresh", "export_health"} <= op_names

    async def test_health_export_route_creates_zip_upload(
        self,
        pool,
        v5_health_route_client,
        health_route_actor,
    ):
        from app.infra.globals import UPLOAD_FOLDER

        async with pool.acquire() as conn:
            await _seed_health_metrics(conn)

        v5_health_route_client.authenticate(
            profile_id=health_route_actor.profile_id,
            session_id=health_route_actor.session_id,
        )
        response = await v5_health_route_client.client.post(
            "/v5/health/export",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".zip")
        assert payload["row_count"] >= 2

        assert UPLOAD_FOLDER
        with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload["content"]))) as archive:
            assert sorted(archive.namelist()) == ["health.csv", "metrics.csv"]

    async def test_health_refresh_route_returns_invalidated_tags(
        self,
        v5_health_route_client,
        health_route_actor,
    ):
        v5_health_route_client.authenticate(
            profile_id=health_route_actor.profile_id,
            session_id=health_route_actor.session_id,
        )

        response = await v5_health_route_client.client.post(
            "/v5/health/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "health,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["health_mv"]
        assert payload["invalidated_tags"] == ["health", "artifacts"]
