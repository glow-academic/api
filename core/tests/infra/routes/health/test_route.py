"""End-to-end tests for the canonical health HTTP routes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from tests.infra.route_helpers import create_admin_route_actor


async def _seed_health_metrics(conn, redis) -> None:
    from app.tools.entries.health.create import create_health
    from app.tools.entries.metrics.create import create_metrics_entry_internal
    from app.tools.entries.metrics.refresh import refresh_metrics_internal

    await create_health(
        conn,
        redis,
        service="redis",
        ok=True,
        latency_ms=12.5,
        ts=datetime(2031, 1, 1, 10, 0, tzinfo=UTC),
    )
    await create_metrics_entry_internal(
        conn,
        redis,
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
        redis_client,
        health_route_client,
        health_route_actor,
    ):
        async with pool.acquire() as conn:
            await _seed_health_metrics(conn, redis_client)

        health_route_client.authenticate(
            profile_id=health_route_actor.profile_id,
            session_id=health_route_actor.session_id,
        )
        response = await health_route_client.client.post(
            "/health",
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

    # NOTE: removed test_health_docs_route_returns_composed_docs,
    # test_health_export_route_creates_zip_upload, and
    # test_health_refresh_route_returns_invalidated_tags — the health
    # docs/export/refresh operations were consolidated into the system parent
    # (`/system/context`, view-aware `/system/export`, `/system/refresh`). The
    # health artifact exposes only the root `POST /health` bundle; there are no
    # `/health/{docs,export,refresh}` routes and the health route client mounts
    # only the root health module.
