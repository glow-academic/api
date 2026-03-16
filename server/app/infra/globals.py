"""Infrastructure singletons and accessor functions.

This module owns all shared global state: database pool, Redis client,
Socket.IO instance, internal event bus, upload directories, and in-memory
stores. Every other module imports from here — never from app.main.
"""

import asyncio
import datetime
import logging
import os
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import asyncpg  # type: ignore
import socketio  # type: ignore
from dotenv import load_dotenv

if TYPE_CHECKING:  # pragma: no cover
    pass

# Redis is nice in production, but optional in dev
try:
    from socketio import AsyncRedisManager
except ImportError:
    AsyncRedisManager = None  # type: ignore

try:
    import redis.asyncio as redis  # type: ignore
except ImportError:
    redis = None  # type: ignore

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Upload directories
# ---------------------------------------------------------------------------
IN_DOCKER = os.getenv("DOCKER_ENV") == "1"
PROJECT_ROOT = (
    Path(__file__).resolve().parents[2]
)  # app/globals.py -> app -> server -> project root
BASE_FOLDER = Path("/app") if IN_DOCKER else PROJECT_ROOT
UPLOAD_FOLDER = BASE_FOLDER / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)


def get_upload_folder() -> Path:
    return UPLOAD_FOLDER


AUDIO_FOLDER = UPLOAD_FOLDER / "audio"
AUDIO_FOLDER.mkdir(parents=True, exist_ok=True)

IMAGE_FOLDER = UPLOAD_FOLDER / "image"
IMAGE_FOLDER.mkdir(parents=True, exist_ok=True)

VIDEO_FOLDER = UPLOAD_FOLDER / "video"
VIDEO_FOLDER.mkdir(parents=True, exist_ok=True)

CALL_FOLDER = UPLOAD_FOLDER / "call"
CALL_FOLDER.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Internal event bus
# ---------------------------------------------------------------------------
InternalHandler = Callable[[dict[str, Any]], Awaitable[None]]


class InternalBus:
    """Simple in-process event bus for triggering handlers internally."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[InternalHandler]] = {}

    def on(self, event: str) -> Callable[[InternalHandler], InternalHandler]:
        def decorator(fn: InternalHandler) -> InternalHandler:
            self._handlers.setdefault(event, []).append(fn)
            return fn

        return decorator

    async def emit(self, event: str, data: dict[str, Any]) -> None:
        handlers = self._handlers.get(event, [])
        if not handlers:
            logger.warning(f"[InternalBus] No handlers registered for event: {event}")
            return
        for handler in handlers:
            try:
                await handler(data)
            except Exception as e:
                logger.error(
                    f"[InternalBus] Error in handler for event '{event}': {e}",
                    exc_info=True,
                )


internal_sio = InternalBus()


def get_internal_sio() -> InternalBus:
    return internal_sio


# ---------------------------------------------------------------------------
# Socket.IO
# ---------------------------------------------------------------------------
origin = os.getenv("ORIGIN", "http://localhost:3000")
app_prefix = os.getenv("APP_PREFIX", "").strip("/")
socket_path = f"{app_prefix}/socket.io" if app_prefix else "socket.io"

redis_url = os.getenv("REDIS_URL")
logger.info(f"redis URL {redis_url}")

if redis_url and AsyncRedisManager:
    logger.info(f"Socket.IO: clustering via Redis → {redis_url}")
    redis_manager = AsyncRedisManager(redis_url)
else:
    logger.info("Socket.IO: no REDIS_URL - using in-memory manager")
    redis_manager = None

_sio_kwargs: dict[str, Any] = {}
if redis_manager is not None:
    _sio_kwargs["client_manager"] = redis_manager

sio = socketio.AsyncServer(
    **_sio_kwargs,
    cors_allowed_origins=["*"],
    cors_credentials=False,
    logger=True,
    engineio_logger=True,
    async_mode="asgi",
    transports=["websocket", "polling"],
    allow_upgrades=True,
    ping_timeout=60,
    ping_interval=25,
    engineio_options={
        "max_http_buffer_size": 1000000,
        "ping_timeout": 60,
        "ping_interval": 25,
        "compression": False,
        "cookie": False,
    },
)


def get_sio_instance() -> socketio.AsyncServer:
    return sio


# ---------------------------------------------------------------------------
# Redis client (HTTP caching, health checks)
# ---------------------------------------------------------------------------
redis_client: Any | None = None


def get_redis_client() -> Any | None:
    return redis_client


# ---------------------------------------------------------------------------
# In-memory stores
# ---------------------------------------------------------------------------
active_results: dict[str, dict[str, Any]] = {}
socket_owner: dict[str, str] = {}
classification_results: dict[str, list[str]] = {}
classification_progress: dict[str, bool] = {}
DEFAULT_CATEGORIES = [
    "homeworks",
    "projects",
    "quizzes",
    "midterms",
    "labs",
    "lectures",
    "syllabi",
]

_voice_message_ids: dict[str, list[str]] = {}
_voice_message_ids_lock = asyncio.Lock()

_simulation_tool_calls: dict[str, dict[str, dict[str, Any]]] = {}
_simulation_tool_calls_locks: dict[str, dict[str, asyncio.Lock]] = {}

_voice_speech_timestamps: dict[str, dict[str, datetime.datetime]] = {}
_voice_speech_timestamps_lock = asyncio.Lock()


def get_socket_owner_dict() -> dict[str, str]:
    return socket_owner


def get_active_results_dict() -> dict[str, dict[str, Any]]:
    return active_results


def get_simulation_tool_calls_dict() -> dict[str, dict[str, dict[str, Any]]]:
    return _simulation_tool_calls


def get_simulation_tool_calls_locks() -> dict[str, dict[str, asyncio.Lock]]:
    return _simulation_tool_calls_locks


def get_voice_speech_timestamps() -> dict[str, dict[str, datetime.datetime]]:
    return _voice_speech_timestamps


def get_voice_speech_timestamps_lock() -> asyncio.Lock:
    return _voice_speech_timestamps_lock


# ---------------------------------------------------------------------------
# Database pool
# ---------------------------------------------------------------------------
_db_pool: asyncpg.Pool | None = None
_test_container: Any | None = None
_test_db_url: str | None = None

_CONTAINER_INFO_FILE = Path("/tmp/glow_test_container.json")  # noqa: S108


def get_pool() -> asyncpg.Pool | None:
    return _db_pool


def _try_reuse_container() -> str | None:
    import json
    import subprocess

    if not _CONTAINER_INFO_FILE.exists():
        return None
    try:
        info = json.loads(_CONTAINER_INFO_FILE.read_text())
        container_id = info["container_id"]
        db_url = info["db_url"]
    except (json.JSONDecodeError, KeyError):
        _CONTAINER_INFO_FILE.unlink(missing_ok=True)
        return None
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container_id],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip() == "true":
            return db_url
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    _CONTAINER_INFO_FILE.unlink(missing_ok=True)
    return None


def _save_container_info(db_url: str) -> None:
    import json

    if _test_container is None:
        return
    container_id = _test_container.get_wrapped_container().id
    _CONTAINER_INFO_FILE.write_text(
        json.dumps({"container_id": container_id, "db_url": db_url})
    )


async def init_db_pool() -> None:
    global _db_pool, _test_container

    env_value = os.getenv("ENV", "")
    env_name = env_value.upper()

    if env_name == "TEST":
        print("🐳 TEST mode detected: starting disposable Postgres with Testcontainers")
        from testcontainers.postgres import PostgresContainer  # type: ignore[import]

        reuse = os.getenv("TESTCONTAINERS_REUSE_ENABLE", "false").lower() == "true"
        global _test_db_url
        db_url: str | None = None

        if reuse:
            db_url = _try_reuse_container()

        if db_url:
            print(f"♻️  Reusing existing container at {db_url}")
        else:
            container = PostgresContainer("postgres:18")
            if reuse:
                container = container.with_kwargs(remove=False)
            _test_container = container
            _test_container.start()

            raw_url = _test_container.get_connection_url()
            db_url = raw_url.replace("postgresql+psycopg2://", "postgresql://")

            if reuse:
                _save_container_info(db_url)

        _test_db_url = db_url
        _db_pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5)
        print(f"✅ Using test database at {db_url}")
        return

    db_user = os.getenv("DB_USER")
    db_password = os.getenv("DB_PASSWORD")
    db_name = os.getenv("DB_NAME")
    db_port = os.getenv("DB_PORT")
    db_host = os.getenv("DB_HOST")

    db_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

    if not all([db_user, db_password, db_name, db_port, db_host]):
        raise ValueError("Database configuration is incomplete")

    using_pgbouncer = db_host == "pgbouncer"
    pgbouncer_pool_mode = os.getenv("PGPOOL_MODE", "transaction").lower()

    print(f"🔌 Initializing asyncpg connection pool to {db_host}:{db_port}/{db_name}")

    pool_config: dict[str, Any] = {
        "min_size": 10,
        "max_size": 100,
        "command_timeout": 60,
        "max_queries": 50000,
        "max_inactive_connection_lifetime": 300,
    }

    if using_pgbouncer and pgbouncer_pool_mode == "transaction":
        pool_config["statement_cache_size"] = 0
        print(
            "   ⚙️  PgBouncer detected (transaction mode): Disabling prepared statements"
        )
    elif using_pgbouncer and pgbouncer_pool_mode == "session":
        print("   ⚙️  PgBouncer detected (session mode): Using prepared statements")
    else:
        print("   ⚙️  Direct connection: Using prepared statements")

    _db_pool = await asyncpg.create_pool(db_url, **pool_config)
    print("✅ Database pool initialized")


async def close_db_pool() -> None:
    global _db_pool, _test_container
    if _db_pool:
        print("🔌 Closing database pool...")
        await _db_pool.close()
        _db_pool = None
        print("✅ Database pool closed")

    if _test_container:
        reuse = os.getenv("TESTCONTAINERS_REUSE_ENABLE", "false").lower() == "true"
        if reuse:
            print("🐳 Container reuse enabled — keeping test container alive")
        else:
            print("🐳 Stopping test database container...")
            _test_container.stop()
            print("✅ Test database container stopped")
        _test_container = None


async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    if not _db_pool:
        raise RuntimeError("Database pool not initialized")
    async with _db_pool.acquire() as connection:
        yield connection


async def expire_all_connections() -> None:
    if _db_pool:
        await _db_pool.expire_connections()
        print("🔄 All pooled connections expired (schema change detected)")


@asynccontextmanager
async def transaction(
    conn: asyncpg.Connection,
) -> AsyncGenerator[asyncpg.Connection, None]:
    tr = conn.transaction()
    await tr.start()
    try:
        yield conn
        await tr.commit()
    except Exception:
        await tr.rollback()
        raise


__all__ = [
    "IMAGE_FOLDER",
]
