"""End-to-end tests for the canonical benchmark HTTP routes."""

from __future__ import annotations

import io
import base64
import zipfile

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
        v5_benchmark_route_client,
        benchmark_route_actor,
    ):
        seeded = await _create_benchmark_route_data(
            pool, redis_client, benchmark_route_actor
        )
        v5_benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await v5_benchmark_route_client.client.post(
            "/v5/benchmark/get",
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

    async def test_search_benchmark_route_returns_history(
        self,
        pool,
        redis_client,
        v5_benchmark_route_client,
        benchmark_route_actor,
    ):
        seeded = await _create_benchmark_route_data(
            pool, redis_client, benchmark_route_actor
        )
        v5_benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await v5_benchmark_route_client.client.post(
            "/v5/benchmark/search",
            json={
                "department_ids": [seeded["department_id"]],
                "history_page": 0,
                "history_page_size": 10,
            },
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Cache-Tags"] == "artifacts,benchmark,search"

        payload = response.json()
        assert payload["page"] == 0
        assert payload["page_size"] == 10
        assert payload["total_count"] >= 0
        assert isinstance(payload["data"], list)

    async def test_benchmark_docs_route_returns_composed_docs(
        self,
        v5_benchmark_route_client,
        benchmark_route_actor,
    ):
        v5_benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await v5_benchmark_route_client.client.post(
            "/v5/benchmark/docs",
            json={"entity_id": None},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["name"] == "benchmark"
        assert payload["type"] == "analytics"
        assert payload["entries"]
        op_names = {operation["name"] for operation in payload["api_operations"]}
        assert {
            "get_benchmark",
            "search_benchmark_history",
            "benchmark_refresh",
            "export_benchmark",
        } <= op_names

    async def test_benchmark_export_route_creates_zip_upload(
        self,
        pool,
        redis_client,
        v5_benchmark_route_client,
        benchmark_route_actor,
    ):
        seeded = await _create_benchmark_route_data(
            pool, redis_client, benchmark_route_actor
        )
        v5_benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await v5_benchmark_route_client.client.post(
            "/v5/benchmark/export",
            json={},
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["content"] != ""
        assert payload["file_name"].endswith(".zip")
        assert payload["row_count"] >= 1

        with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload["content"]))) as archive:
            assert sorted(archive.namelist()) == [
                "benchmarks.csv",
                "test_invocations.csv",
            ]

    async def test_benchmark_refresh_route_returns_invalidated_tags(
        self,
        v5_benchmark_route_client,
        benchmark_route_actor,
    ):
        v5_benchmark_route_client.authenticate(
            profile_id=benchmark_route_actor.profile_id,
            session_id=benchmark_route_actor.session_id,
        )

        response = await v5_benchmark_route_client.client.post(
            "/v5/benchmark/refresh",
            json={},
        )

        assert response.status_code == 200, response.text
        assert response.headers["X-Invalidate-Tags"] == "benchmark,artifacts"
        payload = response.json()
        assert payload["success"] is True
        assert payload["refreshed_views"] == ["benchmark_mv"]
        assert payload["invalidated_tags"] == ["benchmark", "artifacts"]
