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
    route_package: str | None = None,
) -> APIRouter:
    main_dir = Path(__file__).resolve().parents[2] / "app" / "routes"
    package_name = route_package or artifact_name
    package_parts = package_name.split(".")
    _ensure_package_stub("app.routes", main_dir)
    for index, _part in enumerate(package_parts, start=1):
        package_dir = main_dir.joinpath(*package_parts[:index])
        _ensure_package_stub(
            f"app.routes.{'.'.join(package_parts[:index])}",
            package_dir,
        )

    router = APIRouter(prefix=prefix, tags=tags)
    for module_name in module_names:
        module = importlib.import_module(
            f"app.routes.{package_name}.{module_name}"
        )
        router.include_router(module.router)
    return router


@dataclass
class RouteClient:
    """Tiny authenticated HTTP client for route tests."""

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


def _build_artifact_test_app(
    *,
    artifact_router: APIRouter,
    request_state: dict[str, str | None],
    extra_routers: list[APIRouter] | None = None,
) -> FastAPI:
    """Mount a single artifact router with test auth state overrides."""
    from app.infra.identity.middleware import require_auth

    async def _require_auth_override(request: Request) -> None:
        profile_id = request_state["profile_id"]
        if not profile_id:
            raise HTTPException(status_code=401, detail="Missing test profile_id")
        request.state.profile_id = profile_id
        request.state.session_id = request_state["session_id"]

    app = FastAPI()
    root_router = APIRouter(
        prefix="",
        dependencies=[Depends(require_auth)],
    )
    root_router.include_router(artifact_router)
    for extra_router in extra_routers or []:
        root_router.include_router(extra_router)
    app.include_router(root_router)
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
async def persona_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real persona route stack."""
    import app.infra.globals as globals_mod

    persona_router = _build_artifact_router_for_tests(
        artifact_name="persona",
        prefix="/persona",
        tags=["persona"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def scenario_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real scenario route stack."""
    import app.infra.globals as globals_mod

    scenario_router = _build_artifact_router_for_tests(
        artifact_name="scenario",
        prefix="/scenario",
        tags=["scenario"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def agent_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real agent route stack."""
    import app.infra.globals as globals_mod

    agent_router = _build_artifact_router_for_tests(
        artifact_name="agent",
        prefix="/agent",
        tags=["agent"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def group_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real group route stack."""
    import app.infra.globals as globals_mod

    group_router = _build_artifact_router_for_tests(
        artifact_name="group",
        prefix="/group",
        tags=["artifacts", "group"],
        module_names=["get", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def cohort_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real cohort route stack."""
    import app.infra.globals as globals_mod

    cohort_router = _build_artifact_router_for_tests(
        artifact_name="cohort",
        prefix="/cohort",
        tags=["cohort"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def health_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real health route stack."""
    import app.infra.globals as globals_mod

    health_router = _build_artifact_router_for_tests(
        artifact_name="health",
        prefix="/health",
        tags=["health"],
        module_names=["get", "export", "refresh"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def attempt_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real attempt route stack."""
    import app.infra.globals as globals_mod

    attempt_router = _build_artifact_router_for_tests(
        artifact_name="attempt",
        prefix="/attempt",
        tags=["artifacts", "attempt"],
        module_names=[
            "get",
            "archive",
            "refresh",
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
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def test_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real test route stack."""
    import app.infra.globals as globals_mod

    test_router = _build_artifact_router_for_tests(
        artifact_name="test",
        prefix="/test",
        tags=["artifacts", "test"],
        module_names=[
            "get",
            "refresh",
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
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def session_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real session route stack."""
    import app.infra.globals as globals_mod

    session_router = _build_artifact_router_for_tests(
        artifact_name="session",
        prefix="/session",
        tags=["artifacts", "session"],
        module_names=[
            "get",
            "refresh",
            "export",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def events_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the centralized events router."""
    import app.infra.globals as globals_mod

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_events_test_app(request_state=request_state)

    prior_pool = globals_mod._db_pool
    prior_redis = globals_mod.redis_client
    globals_mod._db_pool = pool
    globals_mod.redis_client = redis_client

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as client:
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def benchmark_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real benchmark route stack."""
    import app.infra.globals as globals_mod

    benchmark_router = _build_artifact_router_for_tests(
        artifact_name="benchmark",
        prefix="/benchmark",
        tags=["benchmark"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def pricing_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real pricing route stack."""
    import app.infra.globals as globals_mod

    pricing_router = _build_artifact_router_for_tests(
        artifact_name="pricing",
        route_package="system.pricing",
        prefix="/pricing",
        tags=["pricing"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def reports_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real reports route stack."""
    import app.infra.globals as globals_mod

    reports_router = _build_artifact_router_for_tests(
        artifact_name="reports",
        route_package="attempt.report",
        prefix="/report",
        tags=["report"],
        module_names=["search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def leaderboard_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real leaderboard route stack."""
    import app.infra.globals as globals_mod

    leaderboard_router = _build_artifact_router_for_tests(
        artifact_name="leaderboard",
        prefix="/leaderboard",
        tags=["leaderboard"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def dashboard_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real dashboard route stack."""
    import app.infra.globals as globals_mod

    dashboard_router = _build_artifact_router_for_tests(
        artifact_name="dashboard",
        route_package="attempt.dashboard",
        prefix="/dashboard",
        tags=["dashboard"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def home_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real home route stack."""
    import app.infra.globals as globals_mod

    home_router = _build_artifact_router_for_tests(
        artifact_name="home",
        prefix="/home",
        tags=["artifacts", "home"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def practice_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real practice route stack."""
    import app.infra.globals as globals_mod

    practice_router = _build_artifact_router_for_tests(
        artifact_name="practice",
        prefix="/practice",
        tags=["artifacts", "practice"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def record_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real record route stack."""
    import app.infra.globals as globals_mod

    record_router = _build_artifact_router_for_tests(
        artifact_name="record",
        prefix="/record",
        tags=["artifacts", "record"],
        module_names=["get", "search", "refresh", "export"],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def activity_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real activity route stack."""
    import app.infra.globals as globals_mod

    activity_router = _build_artifact_router_for_tests(
        artifact_name="activity",
        route_package="system.activity",
        prefix="/activity",
        tags=["activity"],
        module_names=[
            "get",
            "search",
            "resolve",
            "refresh",
            "export",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def document_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real document route stack."""
    import app.infra.globals as globals_mod

    document_router = _build_artifact_router_for_tests(
        artifact_name="document",
        prefix="/document",
        tags=["document"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def department_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real department route stack."""
    import app.infra.globals as globals_mod

    department_router = _build_artifact_router_for_tests(
        artifact_name="department",
        prefix="/department",
        tags=["department"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def tool_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real tool route stack."""
    import app.infra.globals as globals_mod

    tool_router = _build_artifact_router_for_tests(
        artifact_name="tool",
        prefix="/tool",
        tags=["tool"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def setting_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real setting route stack."""
    import app.infra.globals as globals_mod

    setting_router = _build_artifact_router_for_tests(
        artifact_name="setting",
        prefix="/setting",
        tags=["setting"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
            "decrypt",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def simulation_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real simulation route stack."""
    import app.infra.globals as globals_mod

    simulation_router = _build_artifact_router_for_tests(
        artifact_name="simulation",
        prefix="/simulation",
        tags=["simulation"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def model_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real model route stack."""
    import app.infra.globals as globals_mod

    model_router = _build_artifact_router_for_tests(
        artifact_name="model",
        prefix="/model",
        tags=["model"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def field_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real field route stack."""
    import app.infra.globals as globals_mod

    field_router = _build_artifact_router_for_tests(
        artifact_name="field",
        prefix="/field",
        tags=["field"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def parameter_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real parameter route stack."""
    import app.infra.globals as globals_mod

    parameter_router = _build_artifact_router_for_tests(
        artifact_name="parameter",
        prefix="/parameter",
        tags=["parameter"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def provider_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real provider route stack."""
    import app.infra.globals as globals_mod

    provider_router = _build_artifact_router_for_tests(
        artifact_name="provider",
        prefix="/provider",
        tags=["provider"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
            "decrypt",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def rubric_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real rubric route stack."""
    import app.infra.globals as globals_mod

    rubric_router = _build_artifact_router_for_tests(
        artifact_name="rubric",
        prefix="/rubric",
        tags=["rubric"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def eval_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real eval route stack."""
    import app.infra.globals as globals_mod

    eval_router = _build_artifact_router_for_tests(
        artifact_name="eval",
        prefix="/eval",
        tags=["eval"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def auth_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real auth route stack."""
    import app.infra.globals as globals_mod

    auth_router = _build_artifact_router_for_tests(
        artifact_name="auth",
        prefix="/auth",
        tags=["auth"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

    globals_mod._db_pool = prior_pool
    globals_mod.redis_client = prior_redis


@pytest_asyncio.fixture
async def profile_route_client(
    pool,
    redis_client,
) -> AsyncGenerator[RouteClient, None]:
    """HTTP client mounted on the real profile route stack."""
    import app.infra.globals as globals_mod
    from app.routes.context import router as context_router
    from app.routes.emulate import router as emulate_router
    from app.routes.unemulate import router as unemulate_router

    profile_router = _build_artifact_router_for_tests(
        artifact_name="profile",
        prefix="/profile",
        tags=["profile"],
        module_names=[
            "get",
            "search",
            "create",
            "update",
            "delete",
            "duplicate",
            "draft",
            "drafts",
            "export",
            "refresh",
        ],
    )

    request_state: dict[str, str | None] = {"profile_id": None, "session_id": None}
    app = _build_artifact_test_app(
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
        yield RouteClient(client=client, _request_state=request_state)

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
