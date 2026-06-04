"""Integration tests for ``resolve_benchmark_context``.

Exercises the benchmark CONTEXT resolver only — that a created benchmark
(with linked profile + department) surfaces in the resolved dashboard context
as a ``benchmarks`` entry, with the linked department hydrated into the
``departments`` resource pair, and that the secondary entry grains
(invocations / tests / test_invocations) come back empty for a bare benchmark
that has no test bridges seeded.
"""

from __future__ import annotations

import pytest

from app.infra.benchmark.context import resolve_benchmark_context
from app.tools.entries.benchmark.create import create_benchmark
from app.tools.entries.benchmark.refresh import refresh_benchmark
from app.tools.resources.departments.create import create_department

pytestmark = pytest.mark.asyncio


class TestResolveBenchmarkContext:
    async def test_returns_benchmark_entry_and_hydrated_department(
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
            created = await create_benchmark(
                conn,
                redis_client,
                profiles_ids=[profile.profile_resource_id],
                departments_ids=[department.id],
            )
            await refresh_benchmark(conn)

        result = await resolve_benchmark_context(
            pool,
            redis_client,
            department_ids=[department.id],
        )

        # The created benchmark is visible in the benchmark grain, scoped by
        # the department filter, and carries its department link back.
        assert result.artifact_id is None
        seeded = next(
            b for b in result.entries["benchmarks"] if b.benchmark_id == created.id
        )
        assert department.id in (seeded.department_ids or [])

        # The linked department is hydrated by name into the resource pair.
        selected_depts = result.resources["departments"].selected
        assert department.id in [d.id for d in selected_depts]
        assert (
            next(d for d in selected_depts if d.id == department.id).name
            == "Benchmark Department"
        )

    async def test_bare_benchmark_has_no_test_or_invocation_entries(
        self, pool, redis_client, profile_identity_factory
    ):
        # A benchmark with no benchmark_test bridges resolves no downstream
        # test / invocation / test_invocation rows (those grains are driven by
        # the benchmark→test bridge, which this benchmark never seeds).
        profile = await profile_identity_factory()

        async with pool.acquire() as conn:
            department = await create_department(
                conn,
                name="Bare Benchmark Department",
                description="Bench dept",
                redis=redis_client,
            )
            created = await create_benchmark(
                conn,
                redis_client,
                profiles_ids=[profile.profile_resource_id],
                departments_ids=[department.id],
            )
            await refresh_benchmark(conn)

        result = await resolve_benchmark_context(
            pool,
            redis_client,
            department_ids=[department.id],
        )

        assert any(
            b.benchmark_id == created.id for b in result.entries["benchmarks"]
        )
        # No test bridge → no tests, no test_invocations for this scope.
        # (invocations is benchmark-scoped via search_invocations on this
        # benchmark id, which likewise has none.)
        assert result.entries["benchmark_tests"] == []
        assert result.entries["invocations"] == []
        assert result.entries["tests"] == []
        assert result.entries["test_invocations"] == []
