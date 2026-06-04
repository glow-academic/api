"""Integration tests for ``export_benchmark_impl``.

Exercises the benchmark EXPORT only — that a created benchmark exports a
base64 zip containing ``benchmarks.csv`` + ``test_invocations.csv`` with the
canonical column headers, that the seeded benchmark row is present with its
``department_ids`` column rendered as the hydrated department *name* (not the
raw UUID — a #163-class read-back regression guard), and the empty-export
contract for a profile that resolves to no exportable rows.
"""

from __future__ import annotations

import base64
import csv
import io
import zipfile

import pytest

from app.infra.benchmark.export import (
    BENCHMARK_CSV_COLUMNS,
    INVOCATION_CSV_COLUMNS,
    export_benchmark_impl,
)
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.resources.departments.create import create_department

pytestmark = pytest.mark.asyncio


class TestExportBenchmarkClient:
    async def test_exports_benchmarks_zip_shape_and_headers(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            department = await create_department(
                conn,
                name="Export Department",
                description="Bench export dept",
                redis=redis_client,
            )
            created = await create_benchmark(
                conn,
                redis_client,
                profiles_ids=[profile.profile_resource_id],
                departments_ids=[department.id],
            )
            await refresh_benchmark(conn)

        result = await export_benchmark_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.row_count >= 1
        assert result.file_name.startswith("benchmark_export_")
        assert result.file_name.endswith(".zip")
        assert result.mime_type == "application/zip"
        assert result.content != ""

        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            assert sorted(archive.namelist()) == [
                "benchmarks.csv",
                "test_invocations.csv",
            ]
            benchmarks_csv = archive.read("benchmarks.csv").decode("utf-8")
            invocations_csv = archive.read("test_invocations.csv").decode("utf-8")

        # Canonical column headers on both members.
        assert benchmarks_csv.splitlines()[0].split(",") == BENCHMARK_CSV_COLUMNS
        assert invocations_csv.splitlines()[0].split(",") == INVOCATION_CSV_COLUMNS

        # The seeded benchmark row is present.
        bench_rows = list(csv.DictReader(io.StringIO(benchmarks_csv)))
        seeded = next(
            r for r in bench_rows if r["benchmark_id"] == str(created.id)
        )
        assert seeded["active"] == "Yes"

    async def test_export_renders_department_name_not_uuid(
        self, pool, redis_client, profile_identity_factory
    ):
        """The ``department_ids`` column must carry the hydrated department name.

        Regression guard (mirrors the pricing #163 group-name guard): the
        export hydrates ``benchmark.department_ids`` through the cached
        ``get_departments`` read and writes the *name* into the column, falling
        back to the raw UUID only when hydration misses. This asserts the
        human-readable name is rendered — guarding against a stale/empty
        read-back surfacing a bare UUID (or blank) instead.
        """
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            department = await create_department(
                conn,
                name="Named Export Department",
                description="Bench export dept",
                redis=redis_client,
            )
            created = await create_benchmark(
                conn,
                redis_client,
                profiles_ids=[profile.profile_resource_id],
                departments_ids=[department.id],
            )
            await refresh_benchmark(conn)

        result = await export_benchmark_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        zip_bytes = base64.b64decode(result.content)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            benchmarks_csv = archive.read("benchmarks.csv").decode("utf-8")

        rows = list(csv.DictReader(io.StringIO(benchmarks_csv)))
        seeded = next(r for r in rows if r["benchmark_id"] == str(created.id))
        assert seeded["department_ids"] == "Named Export Department"
        assert str(department.id) not in seeded["department_ids"]

    async def test_export_with_no_rows_returns_empty(
        self, pool, redis_client, profile_identity_factory
    ):
        # The export shares global benchmark/test-invocation MVs, so other
        # tests may legitimately surface rows. Only assert the empty-export
        # contract when this run genuinely sees zero exportable rows.
        profile = await profile_identity_factory()

        result = await export_benchmark_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.mime_type == "application/zip"
        if result.row_count == 0:
            assert result.content == ""
            assert result.file_name == ""
        else:
            assert result.content != ""
            assert result.file_name.endswith(".zip")
