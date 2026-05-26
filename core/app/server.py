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
import re
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


class _StreamingEventFilter(logging.Filter):
    """Collapse high-frequency streaming deltas into a summary line."""

    _DELTA_EVENTS = (
        "attempt.generate.text.progress",
        "attempt.generate.call.progress",
        # Audio streams — mic frames inbound, assistant audio outbound.
        "attempt.chat.speak",
        "attempt.generate.audio.progress",
        "attempt.chat.assistant_audio",
    )
    _BOUNDARY_EVENTS = (
        "attempt.generate.text.start",
        "attempt.generate.text.complete",
        "attempt.generate.call.start",
        "attempt.generate.call.complete",
        "attempt.generate.audio.session_start",
        "attempt.generate.audio.session_complete",
        "attempt.generate.audio.complete",
        "attempt.chat.voice_ready",
        "attempt.chat.voice_ended",
    )

    # Per-event labels used in the collapsed summary line.
    _EVENT_LABELS = {
        "attempt.generate.text.progress": "text deltas",
        "attempt.generate.call.progress": "call deltas",
        "attempt.chat.speak": "mic frames",
        "attempt.generate.audio.progress": "assistant audio frames",
        "attempt.chat.assistant_audio": "assistant audio frames",
    }

    def __init__(self) -> None:
        super().__init__()
        self._counts: dict[str, int] = {}

    def _flush_summary(self, record: logging.LogRecord) -> None:
        if not self._counts:
            return
        parts = [f"{count} {name}" for name, count in self._counts.items()]
        summary = ", ".join(parts)
        record.msg = f"  ↳ [streaming] {summary}\n{record.msg}"
        self._counts.clear()

    _ACK_PATTERN = re.compile(r"Sending packet MESSAGE data \d+\[\]\s*$")

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()

        # Binary payload lines (audio frames carried as socket.io binary
        # attachments) — always useless in text logs.
        if "<binary>" in msg or "Received packet MESSAGE data 51-" in msg:
            return False

        # Empty engine.io ACK frames — one per event, no useful content.
        if self._ACK_PATTERN.search(msg):
            return False

        # Suppress engineio packet logs for generate + artifact events (payload too large)
        if "Sending packet" in msg and any(
            e in msg for e in (*self._DELTA_EVENTS, *self._BOUNDARY_EVENTS)
        ):
            return False
        if "Sending packet" in msg and any(
            e in msg for e in (".draft.", ".create.", ".update.")
        ):
            return False

        # Count and suppress delta event emits
        for event in self._DELTA_EVENTS:
            if event in msg:
                label = self._EVENT_LABELS.get(event, f"{event} deltas")
                self._counts[label] = self._counts.get(label, 0) + 1
                return False

        # On boundary events, flush the summary
        if any(event in msg for event in self._BOUNDARY_EVENTS):
            self._flush_summary(record)

        return True


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
    """Initialize the Redis client and store it on the globals module.

    Redis is REQUIRED. There is no in-memory fallback — distributed
    state (socket ownership, presence, MV scheduler locks, cache) must
    be authoritative across replicas. If Redis is unavailable at boot,
    we refuse to start so the failure is loud and observable instead
    of silently degrading into split-brain dicts.
    """
    logger_obj.info(
        f"Initializing Redis client: redis={redis_module is not None}, redis_url={redis_url}"
    )
    if not redis_module:
        raise RuntimeError(
            "Redis library is not available. Install `redis` and ensure imports succeed."
        )
    if not redis_url:
        raise RuntimeError(
            "REDIS_URL is not set. Redis is required — no in-memory fallback is supported."
        )

    client = redis_module.from_url(redis_url)  # type: ignore[attr-defined]
    try:
        await client.ping()
    except Exception as e:
        raise RuntimeError(
            f"Failed to reach Redis at {redis_url}: {e!r}. "
            "Redis is required — fix the connection or the app cannot start."
        ) from e
    globals_module.redis_client = client
    logger_obj.info(f"Redis client initialized: {redis_url}")
    return client


def _write_openapi_schema(
    app: FastAPI,
    *,
    get_openapi_fn: Any = get_openapi,
    output_path: Path | None = None,
) -> Path:
    """Generate the OpenAPI schema, add cache tags, and write it to disk."""
    schema = get_openapi_fn(
        title=app.title,
        version=app.version,
        routes=app.routes,
        description="Auto-generated OpenAPI schema from FastAPI API",
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

        # Configure Socket.IO loggers (filter out high-frequency streaming deltas)
        _streaming_filter = _StreamingEventFilter()
        _configure_named_loggers(
            [
                "socketio",
                "engineio",
                "socketio.server",
                "engineio.server",
            ],
            compact_formatter,
        )
        for _sio_logger_name in ["socketio", "engineio", "socketio.server", "engineio.server"]:
            logging.getLogger(_sio_logger_name).addFilter(_streaming_filter)

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
            from app.infra.globals import get_redis_client
            from app.infra.identity.resolve_identity import get_system_session_id

            async with pool.acquire() as conn:
                system_session_id = await get_system_session_id(
                    conn, get_redis_client()
                )
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

        # JWKS prewarm — populate the 60s in-process JWKS cache during
        # startup so the first authenticated request doesn't pay the ~140ms
        # network fetch to Keycloak. Non-blocking: if Keycloak isn't ready
        # the first request will fall through to the lazy fetch (existing
        # behavior). Best-effort cache priming, not a correctness gate.
        try:
            from app.infra.identity.resolve_identity import _get_jwks

            keys = _get_jwks()
            logger.info(f"JWKS prewarm: cached {len(keys)} key(s)")
        except Exception as e:
            logger.warning(f"JWKS prewarm failed (non-blocking, lazy fetch will retry): {e}")

        # MV refresh scheduler — debounces REFRESH MATERIALIZED VIEW calls
        # across the whole instance + replicas. Caller path enqueues O(1)
        # in Redis; one worker per MV per replica drains via Redis lock.
        # All targets registered from the central MV_REGISTRY in
        # app/infra/refresh/config.py — primitives loaded dynamically from
        # `app.tools.entries.{dir}.refresh.{fn}`. No SQL written here.
        import importlib

        from app.infra.refresh.config import MV_REGISTRY
        from app.infra.refresh.scheduler import MVRefresher

        if pool is not None and _globals.redis_client is not None:
            mv_refresher = MVRefresher(pool, _globals.redis_client)
            registered: list[str] = []
            for mv_name, (entries_dir, fn_name, interval_s) in MV_REGISTRY.items():
                try:
                    module = importlib.import_module(
                        f"app.tools.entries.{entries_dir}.refresh"
                    )
                    refresh_fn = getattr(module, fn_name)
                except (ImportError, AttributeError) as e:
                    logger.warning(
                        f"MVRefresher: skipping {mv_name} — could not load "
                        f"app.tools.entries.{entries_dir}.refresh.{fn_name}: {e!r}"
                    )
                    continue
                mv_refresher.register(mv_name, refresh_fn, interval_s=interval_s)
                registered.append(mv_name)
            await stack.enter_async_context(mv_refresher)
            _globals.mv_refresher = mv_refresher
            logger.info(
                f"MVRefresher registered for {len(registered)} MV target(s) "
                f"from MV_REGISTRY"
            )

        # Import MCP server for lifespan management. We register its
        # __aexit__ via a wrapper that times and bounds the teardown so
        # we can distinguish a FastMCP hang from other stages.
        from app.infra.mcp import mcp_server as artifacts_resources_mcp_server

        _mcp_ctx = artifacts_resources_mcp_server.session_manager.run()
        await _mcp_ctx.__aenter__()

        @contextlib.asynccontextmanager
        async def _timed_mcp_teardown():
            try:
                yield
            finally:
                import time as __time
                __start = __time.monotonic()
                try:
                    await asyncio.wait_for(
                        _mcp_ctx.__aexit__(None, None, None),
                        timeout=10.0,
                    )
                    logger.info(
                        f"[shutdown] mcp session_manager ✓ "
                        f"({__time.monotonic() - __start:.2f}s)"
                    )
                except asyncio.TimeoutError:
                    logger.error(
                        f"[shutdown] mcp session_manager HUNG past 10s — "
                        f"FastMCP streamable-HTTP is holding connections. "
                        f"Force-continuing; gunicorn will SIGKILL the worker."
                    )
                except Exception as e:
                    logger.error(
                        f"[shutdown] mcp session_manager errored after "
                        f"{__time.monotonic() - __start:.2f}s: {e!r}"
                    )

        await stack.enter_async_context(_timed_mcp_teardown())

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

        # Start attempt expiry background job
        expire_task: asyncio.Task | None = None
        if pool and _globals.redis_client:
            from app.infra.attempt.expire import expire_loop
            expire_task = asyncio.create_task(expire_loop(pool, _globals.redis_client))
            logger.info("Attempt expiry background job started")

        yield

        # ── Shutdown instrumentation ───────────────────────────────────────
        # Every teardown step is timed and hard-capped. If a stage exceeds
        # its budget the logs show exactly which component is hanging so we
        # can fix the root cause instead of relying on gunicorn SIGKILL.
        import time as _time

        async def _timed_shutdown(label: str, coro, budget_s: float = 10.0) -> None:
            """Await `coro` with a hard timeout; log elapsed + hang diagnosis."""
            start = _time.monotonic()
            try:
                await asyncio.wait_for(coro, timeout=budget_s)
                logger.info(f"[shutdown] {label} ✓ ({_time.monotonic() - start:.2f}s)")
            except asyncio.TimeoutError:
                logger.error(
                    f"[shutdown] {label} HUNG past {budget_s}s budget — "
                    f"root-cause target for the 'Waiting for connections to close' freeze"
                )
            except Exception as e:
                logger.error(
                    f"[shutdown] {label} failed after "
                    f"{_time.monotonic() - start:.2f}s: {e!r}"
                )

        logger.info("[shutdown] lifespan exit begin")
        _shutdown_begin = _time.monotonic()

        # 1. Cancel background tasks and wait for them to finish cancelling
        async def _drain_bg_tasks() -> None:
            reaper_task.cancel()
            monitor_task.cancel()
            if expire_task:
                expire_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await reaper_task
                await monitor_task
                if expire_task:
                    await expire_task

        await _timed_shutdown("background tasks", _drain_bg_tasks(), budget_s=5.0)

        # 2. Close the asyncpg pool. Should be fast unless a query is
        # mid-flight (open transaction held by a streaming tool call).
        await _timed_shutdown("asyncpg pool", close_db_pool(), budget_s=10.0)

        # 3. Close redis client. Normally instant.
        async def _close_redis() -> None:
            if _globals.redis_client:
                await _globals.redis_client.close()
                _globals.redis_client = None

        await _timed_shutdown("redis client", _close_redis(), budget_s=5.0)

        # 4. The AsyncExitStack (entered at lifespan start) will now exit
        # MCP session_manager.run() via its __aexit__. This is the most
        # likely hang source — FastMCP's streamable-HTTP session manager
        # waits for in-flight client streams to close.
        logger.info(
            f"[shutdown] explicit teardown done in "
            f"{_time.monotonic() - _shutdown_begin:.2f}s; "
            f"AsyncExitStack will now unwind MCP session_manager "
            f"(hang here → root cause is FastMCP)"
        )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
from app.version import __version__ as _app_version  # noqa: E402

from fastapi.responses import ORJSONResponse  # noqa: E402

fastapi_app = FastAPI(
    title="GLOW API",
    version=_app_version,
    lifespan=lifespan,
    redirect_slashes=False,
    # orjson is 2-5× faster than the stdlib json module FastAPI uses by
    # default. Hot endpoints serializing 40KB+ Pydantic responses see a
    # measurable shave (~5-10ms warm) per request.
    default_response_class=ORJSONResponse,
)

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
        from app.infra.cache_telemetry import begin_request as _begin_cache_telemetry
        from app.infra.metrics.collector import record_error, record_request
        from app.utils.logging.db_logger import get_logger, set_profile_id

        logger = get_logger(__name__)
        record_error_fn = self._record_error_fn or record_error
        record_request_fn = self._record_request_fn or record_request
        set_profile_id_fn = self._set_profile_id_fn or set_profile_id
        start_time = time.perf_counter()

        # Initialize per-request cache telemetry. Cache helpers
        # (get_cached / set_cached / invalidate_tags) push counts
        # onto this accumulator instead of logging per-event; we emit
        # a single summary line in the finally block below.
        cache_telemetry = _begin_cache_telemetry()

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
        response: Response | None = None
        try:
            response = await call_next(request)
            status_code = response.status_code
            # Attach a compact cache stats header for client-side
            # debugging. Header is short; full summary still goes to
            # the log below.
            if cache_telemetry.total_events > 0:
                response.headers["X-Cache-Stats"] = cache_telemetry.as_header()
            return response
        except Exception as exc:
            status_code = 500
            error_msg = str(exc)
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            # Single summary line per request — replaces the per-event
            # Cache hit/miss/write/invalidate logs that previously
            # flooded the server log on every request.
            if cache_telemetry.total_events > 0:
                logger.info(
                    f"cache req={request.method} {request.url.path} "
                    f"{cache_telemetry.format_summary()}"
                )
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

# Server-Timing: per-request phase timing exposed via W3C Server-Timing
# response header. Code paths register phases via app.infra.server_timing.timed().
from app.infra.server_timing import ServerTimingMiddleware  # noqa: E402

fastapi_app.add_middleware(ServerTimingMiddleware)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
from app.routes import router as root_router  # noqa: E402

fastapi_app.include_router(root_router)

import app.ws  # noqa: E402, F401 — registers ws input/output handlers

# ---------------------------------------------------------------------------
# MCP mount
# ---------------------------------------------------------------------------
from app.routes.mcp import mcp_app  # noqa: E402

fastapi_app.mount("/mcp", mcp_app, name="Artifacts-Resources-MCP")


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
