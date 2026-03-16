"""Integration tests for the health infra wrapper family."""

from __future__ import annotations

import base64
import io
import zipfile
from datetime import UTC, datetime

import pytest

from app.infra.health.context import resolve_health_context
from app.infra.health.docs import docs_health_impl
from app.infra.health.export import export_health_impl
from app.infra.health.refresh import refresh_health_impl
from app.infra.metrics_snapshot import write_health_checks, write_metrics_snapshot
from app.tools.entries.health.create import create_health
from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.refresh import refresh_metrics_internal

pytestmark = pytest.mark.asyncio


async def _seed_health_metrics(conn) -> None:
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


class TestResolveHealthContext:
    async def test_returns_health_and_metrics_entries(self, pool, redis_client):
        async with pool.acquire() as conn:
            await _seed_health_metrics(conn)

        result = await resolve_health_context(
            pool,
            redis_client,
            service="redis",
            date_from=datetime(2031, 1, 1, 0, 0, tzinfo=UTC),
            date_to=datetime(2031, 1, 2, 0, 0, tzinfo=UTC),
        )

        assert result.artifact_id is None
        assert "health" in result.entries
        assert "metrics" in result.entries
        assert result.entries["health"][0].service == "redis"
        assert result.entries["metrics"][0].max_requests_total == 100
        assert result.resources == {}


class TestHealthDocsClient:
    async def test_returns_composed_docs(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await docs_health_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.name == "health"
        assert result.type == "analytics"
        assert result.page_metadata.list.title == "Health"
        assert result.entries[0].name == "health"
        op_names = {operation.name for operation in result.api_operations}
        assert {"get_health", "health_refresh", "export_health"} <= op_names


class TestExportHealthClient:
    async def test_exports_health_and_metrics_zip(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            await _seed_health_metrics(conn)

        result = await export_health_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.row_count >= 2
        assert result.file_name.endswith(".zip")
        assert result.mime_type == "application/zip"
        assert result.content != ""

        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            assert sorted(archive.namelist()) == ["health.csv", "metrics.csv"]
            health_csv = archive.read("health.csv").decode("utf-8")
            metrics_csv = archive.read("metrics.csv").decode("utf-8")

        assert len(health_csv.strip().splitlines()) >= 2
        assert len(metrics_csv.strip().splitlines()) >= 2
        assert "redis" in health_csv
        assert "100" in metrics_csv


class TestRefreshHealthClient:
    async def test_refreshes_views_and_invalidates_tags(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await refresh_health_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.success is True
        assert result.refreshed_views == ["health_mv"]
        assert result.invalidated_tags == ["health", "artifacts"]


class TestWriteMetricsSnapshot:
    async def test_writes_metrics_entry(self, pool):
        ts = datetime(2031, 6, 1, 12, 0, tzinfo=UTC)

        result = await write_metrics_snapshot(
            pool,
            ts=ts,
            requests_total=200,
            errors_total=5,
            avg_latency_ms=30.0,
            cpu_percent=50.0,
            memory_bytes=999999,
        )

        assert result.ts is not None


class TestWriteHealthChecks:
    async def test_writes_health_entries(self, pool):
        from types import SimpleNamespace

        ts = datetime(2031, 6, 1, 12, 0, tzinfo=UTC)
        checks = {
            "redis": SimpleNamespace(ok=True, latency_ms=5.0, error=""),
            "database": SimpleNamespace(ok=False, latency_ms=100.0, error="timeout"),
        }

        await write_health_checks(pool, ts=ts, checks=checks)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT service, ok, error FROM health_entry WHERE ts = $1 ORDER BY service",
                ts,
            )

        assert len(rows) == 2
        assert rows[0]["service"] == "database"
        assert rows[0]["ok"] is False
        assert rows[0]["error"] == "timeout"
        assert rows[1]["service"] == "redis"
        assert rows[1]["ok"] is True
