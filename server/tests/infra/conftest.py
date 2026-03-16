"""Shared fixtures for infra integration tests.

Uses black-box tool functions to set up real test data.
All data lives in the disposable testcontainers DB.
"""

import importlib
import sys
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from uuid import UUID

import pytest
import pytest_asyncio
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from httpx import ASGITransport, AsyncClient

from .factories import (
    create_persona_context_fixture,
    create_profile_identity_fixture,
    create_setting_graph_fixture,
    create_system_graph_fixture,
)

pytestmark = pytest.mark.asyncio


def _ensure_package_stub(package_name: str, package_path: Path) -> None:
    if package_name in sys.modules:
        return
    package = ModuleType(package_name)
    package.__path__ = [str(package_path)]  # type: ignore[attr-defined]
    sys.modules[package_name] = package


def _build_artifact_router_for_tests(
    *,
    artifact_name: str,
    prefix: str,
    tags: list[str],
    module_names: list[str],
) -> APIRouter:
    main_dir = Path(__file__).resolve().parents[2] / "app" / "routes" / "v5"
    artifact_dir = main_dir / artifact_name
    _ensure_package_stub("app.routes.v5", main_dir)
    _ensure_package_stub(f"app.routes.v5.{artifact_name}", artifact_dir)

    router = APIRouter(prefix=prefix, tags=tags)
    for module_name in module_names:
        module = importlib.import_module(
            f"app.routes.v5.{artifact_name}.{module_name}"
        )
        router.include_router(module.router)
    return router


@dataclass
class V5RouteClient:
    """Tiny authenticated HTTP client for v5 route tests."""

    client: AsyncClient
    _request_state: dict[str, str | None]

    def authenticate(
        self,
        *,
        profile_id: UUID | str,
        session_id: UUID | str | None = None,
    ) -> None:
        self._request_state["profile_id"] = str(profile_id)
        self._request_state["session_id"] = (
            str(session_id) if session_id is not None else None
        )


def _build_v5_artifact_test_app(
    *,
    artifact_router: APIRouter,
    request_state: dict[str, str | None],
    extra_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Mount a single v5 artifact router with test auth state overrides."""
    from app.infra.identity.middleware import require_auth

    async def _require_auth_override(request: Request) -> None:
        profile_id = request_state["profile_id"]
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing test profile_id")
        request.state.profile_id = profile_id
        request.state.session_id = request_state["session_id"]

    app = FastAPI()
    root_router = APIRouter(
        prefix="/v5",
        dependencies=[Depends(require_auth)],
    )
    root_router.include_router(artifact_router)
    for extra_router in extra_routers or []:
        root_router.include_router(extra_router)
    app.include_router(root_router)
    app.dependency_overrides[require_auth] = _require_auth_override
    return app


def _build_v5_events_test_app(
    *,
    request_state: dict[str, str | None],
) -> FastAPI:
    """Mount the centralized v5 events router with test auth state overrides."""
    from app.infra.identity.middleware import require_auth

    async def _require_auth_override(request: Request) -> None:
        profile_id = request_state["profile_id"]
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing test profile_id")
        request.state.profile_id = profile_id
        request.state.session_id = request_state["session_id"]

    from app.routes.stream import router as stream_router

    app = FastAPI()
    app.include_router(
        stream_router,
        dependencies=[Depends(require_auth)],
    )
    app.dependency_overrides[require_auth] = _require_auth_override
    return app


@pytest.fixture(autouse=True)
def _redirect_audit_upload_folder(monkeypatch, tmp_path):
    """Keep audited route tests from writing uploads into server/uploads."""
    import app.infra.globals as globals_mod

    monkeypatch.setattr(globals_mod, "UPLOAD_FOLDER", tmp_path)


@pytest_asyncio.fixture
async def name_id(pool, redis_client) -> UUID:
    """Create a fresh name resource via black-box tool."""
    from app.tools.resources.names.create import create_name

    async with pool.acquire() as conn:
        result = await create_name(conn, "Test Name", redis_client)
    return result.id


@pytest_asyncio.fixture
async def description_id(pool, redis_client) -> UUID:
    """Create a fresh description resource via black-box tool."""
    from app.tools.resources.descriptions.create import create_description

    async with pool.acquire() as conn:
        result = await create_description(conn, "Test description", redis_client)
    return result.id


@pytest_asyncio.fixture
async def profile_identity_factory(pool, redis_client):
    """Create real profile artifacts plus linked resources for context tests."""

    return lambda **kwargs: create_profile_identity_fixture(
        pool,
        redis_client,
        **kwargs,
    )


@pytest_asyncio.fixture
async def setting_graph_factory(pool, redis_client):
    """Create a real profile -> setting -> system -> agent -> tool graph."""

    return lambda **kwargs: create_setting_graph_fixture(
        pool,
        redis_client,
        **kwargs,
    )


@pytest_asyncio.fixture
async def system_graph_factory(pool, redis_client):
    """Create a real system -> agent -> model/provider/tool graph."""

    return lambda **kwargs: create_system_graph_fixture(
        pool,
        redis_client,
        **kwargs,
    )


@pytest_asyncio.fixture
async def persona_context_factory(pool, redis_client):
    """Create a real persona artifact plus draft and suggestion resources."""

    return lambda **kwargs: create_persona_context_fixture(
        pool,
        redis_client,
        **kwargs,
    )


@pytest_asyncio.fixture
async def v5_persona_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real persona v5 route stack."""
    import app.infra.globals as globals_mod

    persona_router = _build_artifact_router_for_tests(
        artifact_name="persona",
        prefix="/personas",
        tags=["personas"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=persona_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_scenario_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real scenario v5 route stack."""
    import app.infra.globals as globals_mod

    scenario_router = _build_artifact_router_for_tests(
        artifact_name="scenario",
        prefix="/scenarios",
        tags=["scenarios"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=scenario_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_agent_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real agent v5 route stack."""
    import app.infra.globals as globals_mod

    agent_router = _build_artifact_router_for_tests(
        artifact_name="agent",
        prefix="/agents",
        tags=["agents"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=agent_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_group_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real group v5 route stack."""
    import app.infra.globals as globals_mod

    group_router = _build_artifact_router_for_tests(
        artifact_name="group",
        prefix="/group",
        tags=["artifacts", "group"],
        module_names=["get", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=group_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_cohort_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real cohort v5 route stack."""
    import app.infra.globals as globals_mod

    cohort_router = _build_artifact_router_for_tests(
        artifact_name="cohort",
        prefix="/cohorts",
        tags=["cohorts"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=cohort_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_health_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real health v5 route stack."""
    import app.infra.globals as globals_mod

    health_router = _build_artifact_router_for_tests(
        artifact_name="health",
        prefix="/health",
        tags=["health"],
        module_names=["get", "docs", "export", "refresh"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=health_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_attempt_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real attempt v5 route stack."""
    import app.infra.globals as globals_mod

    attempt_router = _build_artifact_router_for_tests(
        artifact_name="attempt",
        prefix="/attempt",
        tags=["artifacts", "attempt"],
        module_names=[
            "get",
            "archive",
            "refresh",
            "docs",
            "export",
            "start",
            "next",
            "end",
            "end_all",
            "message",
            "grade",
            "stop",
            "response",
            "use_previous",
            "audio",
            "search",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=attempt_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_test_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real test v5 route stack."""
    import app.infra.globals as globals_mod

    test_router = _build_artifact_router_for_tests(
        artifact_name="test",
        prefix="/test",
        tags=["artifacts", "test"],
        module_names=[
            "get",
            "refresh",
            "docs",
            "export",
            "start",
            "next",
            "run",
            "end",
            "stop",
            "search",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=test_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_session_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real session v5 route stack."""
    import app.infra.globals as globals_mod

    session_router = _build_artifact_router_for_tests(
        artifact_name="session",
        prefix="/session",
        tags=["artifacts", "session"],
        module_names=[
            "get",
            "refresh",
            "docs",
            "export",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=session_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_events_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the centralized v5 events router."""
    import app.infra.globals as globals_mod

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_events_test_app(request_state=request_state)

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_benchmark_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real benchmark v5 route stack."""
    import app.infra.globals as globals_mod

    benchmark_router = _build_artifact_router_for_tests(
        artifact_name="benchmark",
        prefix="/benchmark",
        tags=["benchmark"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=benchmark_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_pricing_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real pricing v5 route stack."""
    import app.infra.globals as globals_mod

    pricing_router = _build_artifact_router_for_tests(
        artifact_name="pricing",
        prefix="/pricing",
        tags=["pricing"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=pricing_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_reports_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real reports v5 route stack."""
    import app.infra.globals as globals_mod

    reports_router = _build_artifact_router_for_tests(
        artifact_name="reports",
        prefix="/reports",
        tags=["reports"],
        module_names=["search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=reports_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_leaderboard_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real leaderboard v5 route stack."""
    import app.infra.globals as globals_mod

    leaderboard_router = _build_artifact_router_for_tests(
        artifact_name="leaderboard",
        prefix="/leaderboard",
        tags=["leaderboard"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=leaderboard_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_dashboard_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real dashboard v5 route stack."""
    import app.infra.globals as globals_mod

    dashboard_router = _build_artifact_router_for_tests(
        artifact_name="dashboard",
        prefix="/dashboard",
        tags=["dashboard"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=dashboard_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_home_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real home v5 route stack."""
    import app.infra.globals as globals_mod

    home_router = _build_artifact_router_for_tests(
        artifact_name="home",
        prefix="/home",
        tags=["artifacts", "home"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=home_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_practice_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real practice v5 route stack."""
    import app.infra.globals as globals_mod

    practice_router = _build_artifact_router_for_tests(
        artifact_name="practice",
        prefix="/practice",
        tags=["artifacts", "practice"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=practice_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_record_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real record v5 route stack."""
    import app.infra.globals as globals_mod

    record_router = _build_artifact_router_for_tests(
        artifact_name="record",
        prefix="/record",
        tags=["artifacts", "record"],
        module_names=["get", "search", "refresh", "export", "docs"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=record_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_activity_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real activity v5 route stack."""
    import app.infra.globals as globals_mod

    activity_router = _build_artifact_router_for_tests(
        artifact_name="activity",
        prefix="/activity",
        tags=["activity"],
        module_names=[
            "get",
            "search",
            "problem",
            "resolve",
            "refresh",
            "export",
            "docs",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=activity_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_document_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real document v5 route stack."""
    import app.infra.globals as globals_mod

    document_router = _build_artifact_router_for_tests(
        artifact_name="document",
        prefix="/documents",
        tags=["documents"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=document_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_department_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real department v5 route stack."""
    import app.infra.globals as globals_mod

    department_router = _build_artifact_router_for_tests(
        artifact_name="department",
        prefix="/departments",
        tags=["departments"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=department_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_tool_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real tool v5 route stack."""
    import app.infra.globals as globals_mod

    tool_router = _build_artifact_router_for_tests(
        artifact_name="tool",
        prefix="/tools",
        tags=["tools"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=tool_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_setting_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real setting v5 route stack."""
    import app.infra.globals as globals_mod

    setting_router = _build_artifact_router_for_tests(
        artifact_name="setting",
        prefix="/settings",
        tags=["settings"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
            "decrypt",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=setting_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_simulation_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real simulation v5 route stack."""
    import app.infra.globals as globals_mod

    simulation_router = _build_artifact_router_for_tests(
        artifact_name="simulation",
        prefix="/simulations",
        tags=["simulations"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=simulation_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_model_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real model v5 route stack."""
    import app.infra.globals as globals_mod

    model_router = _build_artifact_router_for_tests(
        artifact_name="model",
        prefix="/models",
        tags=["models"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=model_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_field_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real field v5 route stack."""
    import app.infra.globals as globals_mod

    field_router = _build_artifact_router_for_tests(
        artifact_name="field",
        prefix="/fields",
        tags=["fields"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=field_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_parameter_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real parameter v5 route stack."""
    import app.infra.globals as globals_mod

    parameter_router = _build_artifact_router_for_tests(
        artifact_name="parameter",
        prefix="/parameters",
        tags=["parameters"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=parameter_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_provider_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real provider v5 route stack."""
    import app.infra.globals as globals_mod

    provider_router = _build_artifact_router_for_tests(
        artifact_name="provider",
        prefix="/providers",
        tags=["providers"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
            "decrypt",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=provider_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_rubric_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real rubric v5 route stack."""
    import app.infra.globals as globals_mod

    rubric_router = _build_artifact_router_for_tests(
        artifact_name="rubric",
        prefix="/rubrics",
        tags=["rubrics"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=rubric_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_eval_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real eval v5 route stack."""
    import app.infra.globals as globals_mod

    eval_router = _build_artifact_router_for_tests(
        artifact_name="eval",
        prefix="/evals",
        tags=["evals"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=eval_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_auth_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real auth v5 route stack."""
    import app.infra.globals as globals_mod

    auth_router = _build_artifact_router_for_tests(
        artifact_name="auth",
        prefix="/auths",
        tags=["auths"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=auth_router,
        request_state=request_state,
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def v5_profile_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[V5RouteClient, None]:
    """HTTP client mounted on the real profile v5 route stack."""
    import app.infra.globals as globals_mod
    from app.routes.v5.context import router as context_router
    from app.routes.v5.emulate import router as emulate_router
    from app.routes.v5.unemulate import router as unemulate_router

    profile_router = _build_artifact_router_for_tests(
        artifact_name="profile",
        prefix="/profiles",
        tags=["profiles"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "docs",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_v5_artifact_test_app(
        artifact_router=profile_router,
        request_state=request_state,
        extra_routers=[context_router, emulate_router, unemulate_router],
    )

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield V5RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def attempt_route_actor(pool, redis_client, setting_graph_factory):
    from tests.infra.route_helpers import create_admin_route_actor

    return await create_admin_route_actor(
        pool,
        redis_client,
        setting_graph_factory,
        group_name="attempt-route",
        role_name_prefix="Attempt Route Admin",
    )
