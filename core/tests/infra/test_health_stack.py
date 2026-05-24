"""Integration tests for the health infra wrapper family."""

from __future__ import annotations

import base64
import io
import zipfile
from datetime import UTC, datetime

import pytest

import app.infra.identity.resolve_identity as ri
from app.infra.health.context import resolve_health_context
from app.infra.health.export import export_health_impl
from app.infra.health.refresh import refresh_health_impl
from app.infra.metrics_snapshot import write_health_checks, write_metrics_snapshot
from app.tools.entries.health.create import create_health
from app.tools.entries.health.refresh import refresh_health_internal
from app.tools.entries.health.search import search_health
from app.tools.entries.metrics.create import create_metrics_entry_internal
from app.tools.entries.metrics.refresh import refresh_metrics_internal
from app.tools.entries.metrics.search import search_metrics

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
    async def test_persists_aggregated_values_for_the_hour(
        self, pool, redis_client
    ):
        """write_metrics_snapshot's contract, observed through the same
        primitive production uses to read it: write a snapshot, refresh
        the MV, search by the hour bracket — exactly one row, max
        counters and aggregate latency match the input.

        Uses `search_metrics` instead of inline SQL on metrics_entry so
        any future schema rename (or change in how the MV projects
        per-minute rows up to hourly aggregates) is caught here.
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
        assert result.ts is not None  # canonical write-response shape

        async with pool.acquire() as conn:
            await refresh_metrics_internal(conn)
            rows = await search_metrics(
                conn, redis_client,
                date_from=ts, date_to=ts, bypass_mv=True,
            )

        # Filter to the row at our specific hour (other tests may have
        # inserted snapshots in unrelated hours).
        matching = [r for r in rows if r.date_hour == ts]
        assert len(matching) == 1, (
            f"Expected one MV row at {ts}, got {len(matching)}"
        )
        row = matching[0]
        assert row.max_requests_total == 200
        assert row.max_errors_total == 5
        assert row.avg_latency_ms == 30.0
        assert row.min_memory_bytes == 999999
        assert row.max_memory_bytes == 999999

    async def test_two_snapshots_in_distinct_hours_produce_two_mv_rows(
        self, pool, redis_client
    ):
        """Snapshots in DIFFERENT hours produce separate aggregated MV
        rows. Guards against a regression where same-hour aggregation
        accidentally collapses two distinct hours (e.g. a TRUNC bug)."""
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
            await refresh_metrics_internal(conn)
            rows = await search_metrics(
                conn, redis_client,
                date_from=ts_early, date_to=ts_late, bypass_mv=True,
            )

        by_hour = {r.date_hour: r for r in rows}
        assert ts_early in by_hour, "early-hour MV row missing"
        assert ts_late in by_hour, "late-hour MV row missing"
        assert by_hour[ts_early].max_requests_total == 10
        assert by_hour[ts_late].max_requests_total == 20

    async def test_reuses_system_session_across_snapshots(
        self, pool, redis_client
    ):
        """The system session is created on first call and reused on
        subsequent calls. Prevents 'unbounded sessions_entry growth
        under steady metrics load' where every snapshot mints a new
        system session.

        Asserted via the module-level cache (`ri._system_session_id`)
        rather than per-row session_id columns in the MV — the MV
        doesn't project session_id, and there's no public primitive
        that exposes system sessions (sessions_mv inner-joins on
        profile, system sessions have no profile)."""
        ri._system_session_id = None  # ensure cold start

        await write_metrics_snapshot(
            pool, redis_client,
            ts=datetime(2031, 8, 1, 9, 0, tzinfo=UTC),
            requests_total=1, errors_total=0,
            avg_latency_ms=1.0, cpu_percent=1.0, memory_bytes=1,
        )
        session_after_first = ri._system_session_id

        await write_metrics_snapshot(
            pool, redis_client,
            ts=datetime(2031, 8, 1, 10, 0, tzinfo=UTC),
            requests_total=2, errors_total=0,
            avg_latency_ms=2.0, cpu_percent=2.0, memory_bytes=2,
        )
        session_after_second = ri._system_session_id

        assert session_after_first is not None
        assert session_after_second == session_after_first, (
            "Second snapshot minted a NEW system session instead of "
            "reusing the cached one — sessions_entry will grow without "
            "bound under continuous metrics writes."
        )


class TestWriteHealthChecks:
    async def test_writes_one_row_per_service(self, pool, redis_client):
        """Each (service, ts) check produces an entry visible through the
        health_mv → `search_health` read path with ok/error/latency
        preserved."""
        from types import SimpleNamespace

        ts = datetime(2031, 6, 1, 12, 0, tzinfo=UTC)
        checks = {
            "redis": SimpleNamespace(ok=True, latency_ms=5.0, error=""),
            "database": SimpleNamespace(
                ok=False, latency_ms=100.0, error="timeout",
            ),
        }

        await write_health_checks(pool, redis_client, ts=ts, checks=checks)

        async with pool.acquire() as conn:
            await refresh_health_internal(conn)
            rows = await search_health(
                conn, redis_client,
                date_from=ts, date_to=ts, bypass_mv=True,
            )

        by_service = {r.service: r for r in rows if r.date_hour == ts}
        assert "redis" in by_service
        assert "database" in by_service

        # Redis check: 1 sample, all ok.
        redis_row = by_service["redis"]
        assert redis_row.check_count == 1
        assert redis_row.ok_count == 1
        assert redis_row.fail_count == 0
        assert redis_row.avg_latency_ms == 5.0
        assert redis_row.latest_ok is True

        # Database check: 1 sample, all fail with the captured error.
        db_row = by_service["database"]
        assert db_row.check_count == 1
        assert db_row.ok_count == 0
        assert db_row.fail_count == 1
        assert db_row.avg_latency_ms == 100.0
        assert db_row.latest_ok is False
        assert db_row.latest_error == "timeout"

    async def test_empty_checks_is_noop(self, pool, redis_client):
        """Passing an empty checks dict writes zero rows. Guards against
        a regression where empty input still creates a placeholder row.
        Verified via `search_health` rather than COUNT(*) inline SQL."""
        ts = datetime(2031, 9, 1, 12, 0, tzinfo=UTC)

        await write_health_checks(pool, redis_client, ts=ts, checks={})

        async with pool.acquire() as conn:
            await refresh_health_internal(conn)
            rows = await search_health(
                conn, redis_client,
                date_from=ts, date_to=ts, bypass_mv=True,
            )

        # Filter to the exact hour we wrote to; other tests write to
        # different hours.
        matching = [r for r in rows if r.date_hour == ts]
        assert matching == []
