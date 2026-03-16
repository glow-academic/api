"""Application factory — owns FastAPI app, lifespan, middleware, and route mounting.

This module builds the complete ASGI application.  ``main.py`` simply re-exports
the ``app`` object created here so that ``uvicorn app.main:app`` keeps working.
"""
# mypy: ignore-errors

import asyncio
import contextlib
import json
import logging
import os
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import socketio  # type: ignore
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from starlette.middleware.base import BaseHTTPMiddleware

from app.infra.globals import (
    close_db_pool,
    get_pool,
    init_db_pool,
    sio,
    socket_path,
)

logger = logging.getLogger(__name__)

# Guarded Redis import to prevent crashes when redis is not installed
try:
    import redis.asyncio as redis  # type: ignore
except ImportError:
    redis = None  # type: ignore


def _configure_named_loggers(
    logger_names: list[str],
    formatter: logging.Formatter,
) -> None:
    """Ensure each named logger uses the supplied formatter."""
    for logger_name in logger_names:
        named_logger = logging.getLogger(logger_name)
        named_logger.propagate = False
        if named_logger.handlers:
            for handler in named_logger.handlers:
                handler.setFormatter(formatter)
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            named_logger.addHandler(handler)


async def _initialize_redis_client(
    *,
    redis_module: Any,
    redis_url: str | None,
    globals_module: Any,
    logger_obj: logging.Logger,
) -> Any:
    """Initialize Redis client and store it on the globals module."""
    logger_obj.info(
        f"Initializing HTTP cache Redis client: redis={redis_module is not None}, redis_url={redis_url}"
    )
    if not redis_module or not redis_url:
        logger_obj.warning(
            "Redis disabled (no lib or no REDIS_URL); using in-memory fallbacks"
        )
        globals_module.redis_client = None
        return None

    try:
        client = redis_module.from_url(redis_url)  # type: ignore[attr-defined]
        await client.ping()
        globals_module.redis_client = client
        logger_obj.info(f"Redis client initialized for HTTP caching: {redis_url}")
        return client
    except Exception as e:
        logger_obj.error(f"Failed to initialize Redis client: {e}", exc_info=True)
        globals_module.redis_client = None
        return None


def _write_openapi_schema(
    app: FastAPI,
    *,
    get_openapi_fn: Any = get_openapi,
    output_path: Path | None = None,
) -> Path:
    """Generate the OpenAPI schema, add cache tags, and write it to disk."""
    schema = get_openapi_fn(
        title=app.title,
        version="0.1.0",
        routes=app.routes,
        description="Auto-generated OpenAPI schema from FastAPI v5 API",
    )

    for _path, path_item in schema.get("paths", {}).items():
        for _method, operation in path_item.items():
            if isinstance(operation, dict) and "tags" in operation:
                tags = operation.get("tags", [])
                if tags:
                    operation["x-cache-tags"] = tags

    effective_output_path = output_path or (
        Path(__file__).resolve().parents[1] / "openapi.json"
    )
    effective_output_path.write_text(json.dumps(schema, indent=2))
    logger.info(f"OpenAPI schema written to {effective_output_path}")
    return effective_output_path


def _build_voice_session_reaper(
    *,
    cleanup_audio_session_fn: Any,
    get_stale_sessions_fn: Any,
    sleep_fn: Any = asyncio.sleep,
    logger_obj: logging.Logger = logger,
    interval_seconds: float = 60.0,
    timeout_seconds: float = 300.0,
) -> Any:
    """Build the background coroutine that reaps stale voice sessions."""

    async def _reap_stale_voice_sessions() -> None:
        while True:
            try:
                await sleep_fn(interval_seconds)
                stale = get_stale_sessions_fn(timeout=timeout_seconds)
                for session in stale:
                    logger_obj.info(
                        f"Reaping stale voice session - group_id={session.group_id}"
                    )
                    await cleanup_audio_session_fn(session)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger_obj.error(f"Voice session reaper error: {e}")

    return _reap_stale_voice_sessions


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[Any]:
    async with contextlib.AsyncExitStack() as stack:
        # Configure uvicorn loggers to use compact format
        compact_formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
        _configure_named_loggers(
            ["uvicorn", "uvicorn.error", "uvicorn.access"],
            compact_formatter,
        )

        # Configure Socket.IO loggers
        _configure_named_loggers(
            [
                "socketio",
                "engineio",
                "socketio.server",
                "engineio.server",
            ],
            compact_formatter,
        )

        # Initialize Redis client for HTTP caching and socket ownership management
        import app.infra.globals as _globals

        redis_url = os.getenv("REDIS_URL")
        await _initialize_redis_client(
            redis_module=redis,
            redis_url=redis_url,
            globals_module=_globals,
            logger_obj=logger,
        )

        # Initialize asyncpg database pool
        await init_db_pool()

        pool = get_pool()

        # Initialize system session (for background tasks like health checks, metrics)
        if pool:
            from app.infra.identity.resolve_identity import get_system_session_id

            async with pool.acquire() as conn:
                system_session_id = await get_system_session_id(conn)
                logger.info(f"System session initialized: {system_session_id}")

        # Initialize metrics collector
        from app.infra.metrics.collector import initialize_metrics

        if pool:
            await initialize_metrics(pool, _globals.redis_client)
            logger.info("Metrics collector initialized")

        # Perform Keycloak sync (runs during startup)
        try:
            from app.infra.identity.keycloak_sync import perform_keycloak_sync

            result = await perform_keycloak_sync(department_id=None)
            if result.success:
                logger.info(f"Keycloak sync: {result.message}")
            else:
                logger.warning(f"Keycloak sync failed: {result.message}")
        except Exception as e:
            logger.warning(f"Keycloak sync error (non-blocking): {e}")

        # Import MCP server for lifespan management
        from app.infra.mcp import mcp_server as artifacts_resources_mcp_server

        await stack.enter_async_context(
            artifacts_resources_mcp_server.session_manager.run()
        )

        # Generate OpenAPI schema and write to disk
        _write_openapi_schema(app)

        # Start voice session reaper (cleans up idle sessions every 60s)
        from app.infra.websocket.audio_lifecycle import cleanup_audio_session
        from app.infra.websocket.session_store import get_stale_sessions

        reaper_task = asyncio.create_task(
            _build_voice_session_reaper(
                cleanup_audio_session_fn=cleanup_audio_session,
                get_stale_sessions_fn=get_stale_sessions,
                logger_obj=logger,
            )()
        )

        # Start periodic monitor (health checks + metrics snapshot every 60s)
        async def _periodic_monitor() -> None:
            while True:
                try:
                    await asyncio.sleep(60)
                    from app.infra.metrics.collector import (
                        log_health_checks,
                        log_metrics_snapshot,
                    )

                    await log_metrics_snapshot()
                    await log_health_checks()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Periodic monitor error: {e}")

        monitor_task = asyncio.create_task(_periodic_monitor())

        yield

        # Stop background tasks
        reaper_task.cancel()
        monitor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reaper_task
            await monitor_task

        await close_db_pool()

        if _globals.redis_client:
            await _globals.redis_client.close()
            _globals.redis_client = None
            logger.info("Redis client closed")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
fastapi_app = FastAPI(title="GLOW API", lifespan=lifespan, redirect_slashes=False)

fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# DB Logging middleware
# ---------------------------------------------------------------------------
class DBLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware that automatically logs all requests/responses to database."""

    def __init__(
        self,
        app: Any,
        *,
        record_error_fn: Any | None = None,
        record_request_fn: Any | None = None,
        set_profile_id_fn: Any | None = None,
    ) -> None:
        super().__init__(app)
        self._record_error_fn = record_error_fn
        self._record_request_fn = record_request_fn
        self._set_profile_id_fn = set_profile_id_fn

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        from app.infra.metrics.collector import record_error, record_request
        from app.utils.logging.db_logger import get_logger, set_profile_id

        logger = get_logger(__name__)
        record_error_fn = self._record_error_fn or record_error
        record_request_fn = self._record_request_fn or record_request
        set_profile_id_fn = self._set_profile_id_fn or set_profile_id
        start_time = time.perf_counter()

        profile_id: str | None = None

        content_type = request.headers.get("Content-Type", "")
        is_binary_content = (
            content_type == "application/offset+octet-stream"
            or content_type.startswith("multipart/")
            or content_type.startswith("image/")
            or content_type.startswith("video/")
            or content_type.startswith("audio/")
        )

        if request.method in ("POST", "PUT", "PATCH") and not is_binary_content:
            try:
                body = await request.body()
                if body:
                    body_json = json.loads(body)
                    profile_id = (
                        body_json.get("profileId")
                        or body_json.get("profile_id")
                        or body_json.get("actualProfileId")
                        or body_json.get("effectiveProfileId")
                    )
            except (json.JSONDecodeError, UnicodeDecodeError, KeyError, AttributeError):
                pass

        if hasattr(request.state, "profile_id") and request.state.profile_id:
            profile_id = request.state.profile_id
        else:
            if not profile_id:
                profile_id = request.headers.get("X-Profile-Id")

        if profile_id:
            set_profile_id_fn(profile_id)
        else:
            set_profile_id_fn(None)

        status_code = 500
        error_msg: str | None = None
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as exc:
            status_code = 500
            error_msg = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            try:
                if status_code >= 500:
                    asyncio.create_task(record_error_fn())
                asyncio.create_task(record_request_fn(duration_ms))
            except Exception:
                pass
            finally:
                set_profile_id_fn(None)


fastapi_app.add_middleware(DBLoggingMiddleware)

# Add MCP OAuth middleware
from app.infra.mcp.oauth import McpOAuthMiddleware  # noqa: E402

fastapi_app.add_middleware(McpOAuthMiddleware)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
from app.routes import router as root_router  # noqa: E402

fastapi_app.include_router(root_router)

import app.ws  # noqa: E402, F401 — registers ws/v5 input/output handlers

# ---------------------------------------------------------------------------
# MCP mount
# ---------------------------------------------------------------------------
from app.routes.mcp import mcp_app  # noqa: E402

fastapi_app.mount("/v5", mcp_app, name="Artifacts-Resources-MCP")


# ---------------------------------------------------------------------------
# Combined ASGI app (Socket.IO + FastAPI)
# ---------------------------------------------------------------------------
app = socketio.ASGIApp(sio, fastapi_app, socketio_path=socket_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    force=True,
)

eval_logger = logging.getLogger("app.agents.generic")
eval_logger.setLevel(logging.INFO)
