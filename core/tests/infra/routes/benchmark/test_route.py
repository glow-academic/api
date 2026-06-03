"""End-to-end tests for the canonical benchmark HTTP routes."""

from __future__ import annotations


import pytest
import pytest_asyncio
from tests.helpers import unique_tag
from tests.infra.route_helpers import create_admin_route_actor


@pytest_asyncio.fixture
async def benchmark_route_actor(pool, redis_client, setting_graph_factory):
    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="benchmark-route",
        role_name_prefix="Benchmark Route Admin",
    )


async def _create_benchmark_route_data(pool, redis_client, actor):
    from app.infra.globals import UPLOAD_FOLDER
    from app.tools.entries.benchmark.create import create_benchmark
    from app.tools.entries.benchmark.refresh import refresh_benchmark
    from app.tools.resources.departments.create import create_department

    async with pool.acquire() as conn:
        department = await create_department(
            conn,
            name=f"Benchmark Department {unique_tag()}",
            description="Benchmark route department",
            redis=redis_client,
        )
        benchmark = await create_benchmark(
            conn,
            redis_client,
            profiles_ids=[actor.profiles_id],
            departments_ids=[department.id],
        )
        await refresh_benchmark(conn)

    return {
        "benchmark_id": str(benchmark.id),
        "department_id": str(department.id),
        "department_name": department.name,
        "upload_folder": UPLOAD_FOLDER,
    }


@pytest.mark.asyncio
class TestBenchmarkRoute:
    async def test_get_benchmark_route_returns_evals_and_departments(
        self,
        pool,
        redis_client,
        benchmark_route_client,
        benchmark_route_actor,
    ):
        seeded = await _create_benchmark_route_data(
            pool, redis_client, benchmark_route_actor
        )
        benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await benchmark_route_client.client.post(
            "/benchmark",
            json={"department_ids": [seeded["department_id"]]},
            headers={"X-Bypass-Cache": "1"},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,benchmark"

        payload = response.json()
        assert payload["departments"]
        assert any(
            department["department_id"] == seeded["department_id"]
            for department in payload["departments"]
        )
        assert payload["history"] is not None
        assert payload["analytics"] is not None

    # NOTE: removed test_search_benchmark_route_returns_history,
    # test_benchmark_docs_route_returns_composed_docs,
    # test_benchmark_export_route_creates_zip_upload, and
    # test_benchmark_refresh_route_returns_invalidated_tags — the benchmark
    # search/docs/export/refresh operations were consolidated into the
    # test/system parents (`/system/sessions`-style lists, `/system/context`,
    # view-aware `/system/export`, `/system/refresh`). The benchmark artifact
    # exposes only the root `POST /benchmark` bundle; there are no
    # `/benchmark/{search,docs,export,refresh}` routes and the benchmark route
    # client mounts only the root benchmark module.
