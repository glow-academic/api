"""Integration tests for the benchmark infra wrapper family."""

from __future__ import annotations

import base64
import io
import zipfile

import pytest

from app.infra.benchmark.context import resolve_benchmark_context
from app.infra.benchmark.docs import docs_benchmark_impl
from app.infra.benchmark.export import export_benchmark_impl
from app.infra.benchmark.refresh import refresh_benchmark_impl
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.resources.departments.create import create_department

pytestmark = pytest.mark.asyncio


class TestResolveBenchmarkContext:
    async def test_returns_benchmark_entries_and_hydrated_departments(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            department = await create_department(
                conn,
                name="Benchmark Department",
                description="Bench dept",
                redis=redis_client,
            )
            await create_benchmark(
                conn,
                profiles_ids=[profile.profile_resource_id],
                departments_ids=[department.id],
            )
            await refresh_benchmark(conn)

        result = await resolve_benchmark_context(
            pool,
            redis_client,
            department_ids=[department.id],
        )

        assert len(result.entries["benchmarks"]) >= 1
        assert (
            result.resources["departments"].selected[0].name == "Benchmark Department"
        )
        assert result.entries["invocations"] == []
        assert result.entries["tests"] == []
        assert result.entries["test_invocations"] == []


class TestBenchmarkDocsClient:
    async def test_returns_composed_docs(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await docs_benchmark_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.name == "benchmark"
        assert result.type == "analytics"
        assert result.page_metadata.list.title == "Benchmarks"
        assert result.entries[0].name == "benchmark"
        api_names = {operation.name for operation in result.api_operations}
        assert {
            "get_benchmark",
            "search_benchmark_history",
            "benchmark_refresh",
            "export_benchmark",
        } <= api_names


class TestExportBenchmarkClient:
    async def test_exports_benchmarks_zip(
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
            await create_benchmark(
                conn,
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

        assert "Export Department" in benchmarks_csv


class TestRefreshBenchmarkClient:
    async def test_refreshes_views_and_invalidates_tags(
        self, pool, redis_client, profile_identity_factory
    ):
        profile = await profile_identity_factory()

        result = await refresh_benchmark_impl(
            pool,
            redis_client,
            profile_id=profile.artifact_id,
        )

        assert result.success is True
        assert result.refreshed_views == ["benchmark_mv"]
        assert result.invalidated_tags == ["benchmark", "artifacts"]
