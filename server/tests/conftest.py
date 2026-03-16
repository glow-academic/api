"""
Pytest configuration and shared fixtures for real database testing.
"""

import os
import sys
import asyncio
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import UUID

import asyncpg  # type: ignore[import]
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

# Load environment variables from .env file if it exists
load_dotenv()

# Disable tracing globally BEFORE importing agents
os.environ["OPENAI_AGENTS_DISABLE_TRACING"] = "1"
# Set SECRET_KEY for encryption/decryption in tests
# This will use SECRET_KEY from .env if available, otherwise use default
os.environ["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "test_secret_key_for_integration_tests"
)
# Ensure Testcontainers-backed DB is used
os.environ["ENV"] = os.getenv("ENV", "TEST")
# Enable container reuse by default for fast local runs
os.environ["TESTCONTAINERS_REUSE_ENABLE"] = os.getenv(
    "TESTCONTAINERS_REUSE_ENABLE", "true"
)
# Ensure header signing works in test environment
os.environ["AUTH_SECRET"] = os.getenv(
    "AUTH_SECRET", "test_secret_key_for_integration_tests"
)

# Add the server directory to Python's path
server_dir = Path(__file__).parent.parent
sys.path.insert(0, str(server_dir))

from app.infra.globals import close_db_pool, init_db_pool  # noqa: E402
from app.utils.test_db import get_test_db_url  # noqa: E402

# Store the test database URL for direct connections
_test_db_url: str | None = None


async def _wait_for_database(
    admin_conn: asyncpg.Connection,
    db_name: str,
    *,
    attempts: int = 20,
    delay_s: float = 0.1,
) -> None:
    """Wait until Postgres reports the cloned database as visible."""
    for _ in range(attempts):
        exists = await admin_conn.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if exists:
            return
        await asyncio.sleep(delay_s)
    raise RuntimeError(f"Cloned test database never became visible: {db_name}")


def _filter_meta_commands(sql: str) -> str:
    """Strip psql meta-commands (lines starting with \\) from SQL."""
    return "\n".join(
        line for line in sql.split("\n") if not line.strip().startswith("\\")
    )


def _concat_schema(schema_dir: Path) -> str:
    """Concatenate split schema files into a single SQL string.

    Load order: extensions → enums → tables → indexes → foreign_keys → views → view indexes.
    """
    parts: list[str] = []

    # extensions.sql
    ext = schema_dir / "extensions.sql"
    if ext.exists():
        parts.append(ext.read_text())

    # Prerequisite functions (needed by table DEFAULT clauses)
    funcs = schema_dir / "functions.sql"
    if funcs.exists():
        parts.append(funcs.read_text())

    # enums/ (sorted)
    enums_dir = schema_dir / "enums"
    if enums_dir.exists():
        for f in sorted(enums_dir.glob("*.sql")):
            parts.append(f.read_text())

    # tables/ and indexes/ share the same subfolder structure
    subfolders = ("artifacts", "entries", "resources", "junctions", "connections")

    for subfolder in subfolders:
        d = schema_dir / "tables" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    for subfolder in subfolders:
        d = schema_dir / "indexes" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    for subfolder in subfolders:
        d = schema_dir / "foreign_keys" / subfolder
        if d.exists():
            for f in sorted(d.glob("*.sql")):
                parts.append(f.read_text())

    # Set search_path for views (they use unqualified table names)
    parts.append("SET search_path = public;")

    # Materialized views (pure CREATE ... WITH NO DATA)
    views_dir = schema_dir / "views"
    if views_dir.exists():
        for f in sorted(views_dir.glob("*.sql")):
            parts.append(f.read_text())

    # MV indexes
    idx_views_dir = schema_dir / "indexes" / "views"
    if idx_views_dir.exists():
        for f in sorted(idx_views_dir.glob("*.sql")):
            parts.append(f.read_text())

    return "\n".join(parts)


# --- CORE TEST FIXTURES ---


@pytest_asyncio.fixture(scope="session", autouse=True)
async def initialize_test_db() -> AsyncGenerator[None, None]:
    """Spin up disposable Postgres via init_db_pool and tear it down.

    Uses a template database to skip schema + seed + bootstrap on warm runs.
    The template is invalidated automatically when any SQL file changes.
    """
    global _test_db_url

    database_dir = Path(__file__).parent.parent.parent / "database"
    schema_dir = database_dir / "schema"

    if not schema_dir.exists():
        raise FileNotFoundError(
            f"Schema directory not found: {schema_dir}\n"
            "Please run 'make split-schema' to generate it."
        )

    # 1. Start / reuse the test container and create a pool to the default DB
    await init_db_pool()

    base_url = get_test_db_url()
    if base_url is None:
        raise RuntimeError("Test database URL not available")

    from app.utils.template_db import (
        cleanup_old_templates,
        clone_from_template,
        compute_db_hash,
        create_fresh_db,
        get_admin_url,
        save_as_template,
        template_exists,
    )

    # 2. Compute content hash
    db_hash = compute_db_hash(database_dir)
    template_name = f"template_glow_{db_hash}"
    worker_id = os.getenv("PYTEST_XDIST_WORKER", "main")
    clone_name = f"test_glow_{db_hash}_{worker_id}_{os.getpid()}"
    admin_url = get_admin_url(base_url)

    print(f"🔑 Template hash: {db_hash}")

    # 3. Connect to admin DB and check for template
    import app.infra.globals as globals_mod

    admin_conn = await asyncpg.connect(admin_url)
    try:
        has_template = await template_exists(admin_conn, template_name)

        if has_template:
            # --- WARM PATH: clone from template ---
            print(f"⚡ Template found: {template_name} — cloning to {clone_name}")
            await clone_from_template(admin_conn, template_name, clone_name)
            await _wait_for_database(admin_conn, clone_name)

            # Reconnect pool to the cloned database
            parsed = urlparse(base_url)
            clone_url = urlunparse(parsed._replace(path=f"/{clone_name}"))

            if globals_mod._db_pool:
                await globals_mod._db_pool.close()
            globals_mod._db_pool = await asyncpg.create_pool(
                clone_url, min_size=1, max_size=5
            )
            globals_mod._test_db_url = clone_url
            _test_db_url = clone_url
            print("✅ Cloned database ready (schema skipped)")
        else:
            # --- COLD PATH: build from scratch, then save as template ---
            print("🏗️  No template found — building from scratch")

            # Create a fresh database to avoid conflicts with stale state
            build_db = f"build_glow_{db_hash}"
            await create_fresh_db(admin_conn, build_db)

            # Reconnect pool to the fresh build database
            parsed = urlparse(base_url)
            build_url = urlunparse(parsed._replace(path=f"/{build_db}"))

            if globals_mod._db_pool:
                await globals_mod._db_pool.close()
            globals_mod._db_pool = await asyncpg.create_pool(
                build_url, min_size=1, max_size=5
            )

            pool = globals_mod._db_pool

            # Keycloak stubs — the real tables are created by Keycloak at startup,
            # but the test DB never runs Keycloak.
            async with pool.acquire() as conn:
                await conn.execute("""
                    CREATE SCHEMA IF NOT EXISTS keycloak;
                    CREATE TABLE IF NOT EXISTS keycloak.org (
                        id text PRIMARY KEY,
                        alias text
                    );
                    CREATE TABLE IF NOT EXISTS keycloak.realm (
                        name text PRIMARY KEY,
                        ssl_required text
                    );
                """)

            schema_sql = _filter_meta_commands(_concat_schema(schema_dir))
            async with pool.acquire() as conn:
                await conn.execute(schema_sql)
            print("🗄️  Test schema applied (from split files)")

            # Refresh all unpopulated materialized views
            # (MVs are created WITH NO DATA by schema load, need initial refresh)
            async with pool.acquire() as conn:
                unpopulated = await conn.fetch(
                    "SELECT matviewname FROM pg_matviews WHERE NOT ispopulated"
                )
                for row in unpopulated:
                    await conn.execute(
                        f'REFRESH MATERIALIZED VIEW "{row["matviewname"]}"'
                    )
            print("🗄️  Materialized views refreshed")

            # Close pool before saving template (terminates connections)
            await globals_mod._db_pool.close()
            globals_mod._db_pool = None

            # Save as template for next run
            await save_as_template(admin_conn, build_db, template_name)
            print(f"💾 Template saved: {template_name}")

            # Clean up old templates (this drops build_glow_* too)
            await cleanup_old_templates(admin_conn, preserve=template_name)

            # Clone from the freshly saved template for the test run
            await clone_from_template(admin_conn, template_name, clone_name)
            await _wait_for_database(admin_conn, clone_name)
            clone_url = urlunparse(parsed._replace(path=f"/{clone_name}"))

            globals_mod._db_pool = await asyncpg.create_pool(
                clone_url, min_size=1, max_size=5
            )
            globals_mod._test_db_url = clone_url
            _test_db_url = clone_url
    finally:
        await admin_conn.close()

    # Fallback: if _test_db_url wasn't set above
    if _test_db_url is None:
        _test_db_url = base_url

    try:
        yield
    finally:
        await close_db_pool()
        _test_db_url = None


@pytest_asyncio.fixture
async def pool() -> AsyncGenerator[asyncpg.Pool, None]:
    """Provide a real asyncpg pool for integration tests.

    Creates a fresh pool per test to avoid event loop issues.
    Tests using this fixture exercise the real pool.acquire() → conn path,
    matching production behavior.
    """
    global _test_db_url

    if _test_db_url is None:
        raise RuntimeError(
            "Test database URL not available. Did initialize_test_db run?"
        )

    test_pool = await asyncpg.create_pool(_test_db_url, min_size=2, max_size=5)
    try:
        yield test_pool
    finally:
        await test_pool.close()


@pytest_asyncio.fixture
async def conn() -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide clean database connection with transaction rollback.

    Each test gets:
    - Connection to database with schema already applied (session level)
    - Transaction that rolls back after test completes (test isolation)

    Creates connections directly instead of using the pool to avoid event loop issues.
    """
    global _test_db_url

    if _test_db_url is None:
        raise RuntimeError(
            "Test database URL not available. Did initialize_test_db run?"
        )

    # Create connection directly (not from pool) to avoid event loop issues
    connection = await asyncpg.connect(_test_db_url)

    tx = connection.transaction()
    await tx.start()
    try:
        yield connection
    finally:
        await tx.rollback()  # Undo all test changes
        await connection.close()


# --- REDIS FIXTURE ---

_redis_container: RedisContainer | None = None
_redis_url: str | None = None


@pytest.fixture(scope="session", autouse=True)
def start_redis_container() -> None:
    """Start a Redis testcontainer for the session."""
    global _redis_container, _redis_url
    container = RedisContainer("redis:7-alpine")
    container = container.with_kwargs(remove=False)
    container.start()
    host = container.get_container_host_ip()
    port = container.get_exposed_port(6379)
    _redis_url = f"redis://{host}:{port}/0"
    _redis_container = container


@pytest_asyncio.fixture
async def redis_client() -> AsyncGenerator[Redis, None]:
    """Provide a clean Redis connection that flushes after each test."""
    if _redis_url is None:
        raise RuntimeError("Redis container not started.")
    client = Redis.from_url(_redis_url)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()


# --- ENTITY FIXTURES ---


@pytest_asyncio.fixture
async def profile_id(conn, redis_client):
    """A fresh profiles_resource ID."""
    from app.tools.resources.profiles.create import create_profile

    profile = await create_profile(conn, redis_client)
    return profile.id


@pytest_asyncio.fixture
async def department_id(conn, redis_client):
    """A fresh departments_resource ID."""
    from app.tools.resources.departments.create import create_department

    dept = await create_department(conn, redis=redis_client)
    return dept.id


@pytest_asyncio.fixture
async def session_id(conn, profile_id):
    """A fresh sessions_entry ID (depends on profile_id)."""
    from app.tools.entries.sessions.create import create_session

    session = await create_session(conn, profile_id=profile_id)
    return session.id


@pytest_asyncio.fixture
async def group_id(conn, session_id):
    """A fresh groups_entry ID (depends on session_id)."""
    from app.tools.entries.groups.create import create_group

    group = await create_group(conn, session_id=session_id)
    return group.id


@pytest_asyncio.fixture
async def run_id(conn, group_id, session_id):
    """A fresh runs_entry ID (depends on group_id, session_id)."""
    from app.tools.entries.runs.create import create_run

    run = await create_run(conn, group_id=group_id, session_id=session_id)
    return run.id


@pytest_asyncio.fixture
async def call_id(conn, run_id, session_id):
    """A fresh calls_entry ID (depends on run_id, session_id)."""
    from app.tools.entries.calls.create import create_call

    call = await create_call(conn, run_id=run_id, session_id=session_id)
    return call.id


@dataclass
class SimulationBundle:
    """All resource IDs needed for practice/home simulation tests."""

    profile_id: UUID
    department_id: UUID
    cohort_id: UUID
    simulation_id: UUID
    simulation_position_id: UUID
    simulation_availability_id: UUID
    profile_persona_id: UUID


@pytest_asyncio.fixture
async def simulation_bundle(conn, redis_client, profile_id, department_id):
    """Create all resources needed for practice/home simulation tests."""
    from datetime import UTC, datetime

    from app.tools.resources.cohorts.create import create_cohort
    from app.tools.resources.personas.create import (
        create_persona as create_persona_resource,
    )
    from app.tools.resources.profile_personas.create import (
        create_profile_persona,
    )
    from app.tools.resources.simulation_availability.create import (
        create_simulation_availability,
    )
    from app.tools.resources.simulation_positions.create import (
        create_simulation_position,
    )
    from app.tools.resources.simulations.create import create_simulation

    cohort = await create_cohort(conn, redis_client)
    simulation = await create_simulation(conn, redis_client)
    sim_position = await create_simulation_position(
        conn, simulation.id, value=1, redis=redis_client
    )
    sim_availability = await create_simulation_availability(
        conn,
        simulation.id,
        time=datetime.now(UTC),
        availability_type="start",
        redis=redis_client,
    )
    persona_resource = await create_persona_resource(conn, redis=redis_client)
    profile_persona = await create_profile_persona(
        conn, profile_id, persona_resource.id, redis=redis_client
    )

    return SimulationBundle(
        profile_id=profile_id,
        department_id=department_id,
        cohort_id=cohort.id,
        simulation_id=simulation.id,
        simulation_position_id=sim_position.id,
        simulation_availability_id=sim_availability.id,
        profile_persona_id=profile_persona.id,
    )


# --- OTHER CONFIG ---


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest markers."""
    config.addinivalue_line("markers", "asyncio: mark test as async")


pytest_plugins = ("pytest_asyncio",)
