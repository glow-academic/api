"""Integration tests for the health infra wrapper family."""

from __future__ import annotations

import base64
import io
import zipfile
from datetime import UTC, datetime

import pytest

from app.infra.health.context import resolve_health_context
from app.infra.health.export import export_health_impl
from app.infra.health.refresh import refresh_health_impl
from app.infra.metrics_snapshot import write_health_checks, write_metrics_snapshot
from app.tools.entries.health.create import create_health
from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.refresh import refresh_metrics_internal

pytestmark = pytest.mark.asyncio


async def _seed_health_metrics(conn, redis_client) -> None:
    await create_health(
        conn,
        redis_client, service="redis",
        ok=True,
        latency_ms=12.5,
        ts=datetime(2031, 1, 1, 10, 0, tzinfo=UTC),
    )
    await create_metrics_entry_internal(
        conn,
        redis_client, ts=datetime(2031, 1, 1, 10, 0, tzinfo=UTC),
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
            await _seed_health_metrics(conn, redis_client)

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


class TestExportHealthClient:
    async def test_exports_health_and_metrics_zip(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            await _seed_health_metrics(conn, redis_client)

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
    async def test_persists_row_with_exact_values(self, pool, redis_client):
        """write_metrics_snapshot writes a metrics_entry row whose columns
        match the input arguments exactly.

        This is the contract: caller passes 6 numeric measurements + a ts;
        a row appears in the database with those values readable back.
        """
        ts = datetime(2031, 6, 1, 12, 0, tzinfo=UTC)

        result = await write_metrics_snapshot(
            pool,
            redis_client,
            ts=ts,
            requests_total=200,
            errors_total=5,
            avg_latency_ms=30.0,
            cpu_percent=50.0,
            memory_bytes=999999,
        )

        # Response carries the row's ts (returned as text by the underlying
        # INSERT ... RETURNING ts::text — see create_metrics_entry_internal).
        assert result.ts is not None

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT ts, requests_total, errors_total, avg_latency_ms,
                       cpu_percent, memory_bytes
                FROM metrics_entry
                WHERE ts = $1
                """,
                ts,
            )

        assert row is not None, "snapshot row not found in metrics_entry"
        assert row["ts"] == ts
        assert row["requests_total"] == 200
        assert row["errors_total"] == 5
        assert row["avg_latency_ms"] == 30.0
        assert row["cpu_percent"] == 50.0
        assert row["memory_bytes"] == 999999

    async def test_two_snapshots_with_distinct_ts_create_distinct_rows(
        self, pool, redis_client
    ):
        """Sequential calls with different timestamps don't overwrite each
        other — each produces its own row. Prevents a regression where an
        UPSERT-on-ts collision could silently drop the older snapshot."""
        ts_early = datetime(2031, 7, 1, 9, 0, tzinfo=UTC)
        ts_late = datetime(2031, 7, 1, 10, 0, tzinfo=UTC)

        await write_metrics_snapshot(
            pool, redis_client,
            ts=ts_early, requests_total=10, errors_total=0,
            avg_latency_ms=5.0, cpu_percent=10.0, memory_bytes=1000,
        )
        await write_metrics_snapshot(
            pool, redis_client,
            ts=ts_late, requests_total=20, errors_total=1,
            avg_latency_ms=8.0, cpu_percent=15.0, memory_bytes=2000,
        )

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT ts, requests_total FROM metrics_entry "
                "WHERE ts IN ($1, $2) ORDER BY ts",
                ts_early, ts_late,
            )

        assert len(rows) == 2
        assert rows[0]["ts"] == ts_early
        assert rows[0]["requests_total"] == 10
        assert rows[1]["ts"] == ts_late
        assert rows[1]["requests_total"] == 20

    async def test_reuses_system_session_across_snapshots(
        self, pool, redis_client
    ):
        """The system session is created on first call and reused on
        subsequent calls. Prevents a regression where every snapshot
        creates a new system session, exploding the sessions_entry table
        and breaking the implicit "one system session per process" model
        documented on get_system_session_id."""
        ts_a = datetime(2031, 8, 1, 9, 0, tzinfo=UTC)
        ts_b = datetime(2031, 8, 1, 10, 0, tzinfo=UTC)

        await write_metrics_snapshot(
            pool, redis_client,
            ts=ts_a, requests_total=1, errors_total=0,
            avg_latency_ms=1.0, cpu_percent=1.0, memory_bytes=1,
        )
        await write_metrics_snapshot(
            pool, redis_client,
            ts=ts_b, requests_total=2, errors_total=0,
            avg_latency_ms=2.0, cpu_percent=2.0, memory_bytes=2,
        )

        async with pool.acquire() as conn:
            session_ids = await conn.fetch(
                "SELECT DISTINCT session_id FROM metrics_entry "
                "WHERE ts IN ($1, $2)",
                ts_a, ts_b,
            )

        assert len(session_ids) == 1, (
            "Both snapshots should share the same system session_id; "
            f"got {len(session_ids)} distinct sessions"
        )


class TestWriteHealthChecks:
    async def test_writes_one_row_per_service(self, pool, redis_client):
        """Each (service, ts) check in the input produces exactly one
        health_entry row with ok/error/latency_ms preserved."""
        from types import SimpleNamespace

        ts = datetime(2031, 6, 1, 12, 0, tzinfo=UTC)
        checks = {
            "redis": SimpleNamespace(ok=True, latency_ms=5.0, error=""),
            "database": SimpleNamespace(ok=False, latency_ms=100.0, error="timeout"),
        }

        await write_health_checks(pool, redis_client, ts=ts, checks=checks)

        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT service, ok, error, latency_ms FROM health_entry "
                "WHERE ts = $1 ORDER BY service",
                ts,
            )

        assert len(rows) == 2
        assert rows[0]["service"] == "database"
        assert rows[0]["ok"] is False
        assert rows[0]["error"] == "timeout"
        assert rows[0]["latency_ms"] == 100.0
        assert rows[1]["service"] == "redis"
        assert rows[1]["ok"] is True
        assert rows[1]["error"] == ""
        assert rows[1]["latency_ms"] == 5.0

    async def test_empty_checks_is_noop(self, pool, redis_client):
        """Passing an empty checks dict writes zero rows. The implementation
        iterates `checks.items()`; this guards against a regression where
        empty input still creates a placeholder row."""
        ts = datetime(2031, 9, 1, 12, 0, tzinfo=UTC)

        await write_health_checks(pool, redis_client, ts=ts, checks={})

        async with pool.acquire() as conn:
            count = await conn.fetchval(
                "SELECT COUNT(*) FROM health_entry WHERE ts = $1", ts,
            )
        assert count == 0
