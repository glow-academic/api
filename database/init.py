"""Atomic seed orchestrator — staging DB + rename swap.

Runs the seed runner against a side staging database (`<db>_staging`),
stamps a marker row, then atomically renames staging → target via
`ALTER DATABASE … RENAME`. Either the target DB ends up with a fully
formed `_glow_seed_complete` marker, or the target DB is untouched
and staging is dropped.

This is the runtime-init counterpart to `make seed-gen` (which uses
testcontainers + pg_dump). The seed runner doesn't change — it just
gets pointed at the staging URL.

Idempotency: marker row in `_glow_seed_complete` (target DB) is the
sole source of truth. Re-runs short-circuit immediately when present.

Required env (read by `__main__`):
  SEED_TARGET_PG_URL     — postgres://user:pw@host:port/<target_db>
  SEED_TARGET_REDIS_URL  — redis://host:port/<n>
  SEED_SETUP             — setup name (default: fresh). Also accepts --setup.

Required postgres perms: the connecting role must have CREATEDB. The
stock postgres:18-alpine image makes POSTGRES_USER a superuser, so
this is satisfied for the standard compose deploy.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from urllib.parse import urlparse, urlunparse

import asyncpg

from database.scripts.runner import main_setup


MARKER_DDL = """
CREATE TABLE IF NOT EXISTS _glow_seed_complete (
    setup TEXT PRIMARY KEY,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""


def _swap_url(url: str, new_path: str) -> str:
    parsed = urlparse(url)
    return urlunparse(parsed._replace(path=new_path))


async def _terminate(conn: asyncpg.Connection, dbname: str) -> None:
    """Boot every backend on dbname so we can rename/drop it."""
    await conn.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = $1 AND pid <> pg_backend_pid()",
        dbname,
    )


async def _existing_setups(conn: asyncpg.Connection) -> list[str]:
    """Return the setups the target DB has already been seeded for.

    Empty list ⇒ either the marker table is absent (never seeded) or it
    exists but has no rows. Either way the swap is free to proceed.
    """
    table_exists = await conn.fetchval(
        "SELECT EXISTS ("
        "  SELECT 1 FROM information_schema.tables "
        "  WHERE table_schema = 'public' AND table_name = '_glow_seed_complete'"
        ")"
    )
    if not table_exists:
        return []
    rows = await conn.fetch("SELECT setup FROM _glow_seed_complete ORDER BY setup")
    return [row["setup"] for row in rows]


def _seed_decision(
    setup: str, existing: list[str], *, force: bool, target_db: str
) -> tuple[str, str]:
    """Decide what to do given the setups already seeded into the target.

    Pure (no I/O) so the guard logic is unit-testable without a DB.
    Returns ``(action, message)`` where action is one of:
      - ``"skip"``     — already seeded for this setup; idempotent no-op.
      - ``"refuse"``   — already seeded for a DIFFERENT setup; the whole-DB
                          swap would discard live data, so refuse.
      - ``"proceed"``  — safe to build staging + swap.
    """
    if setup in existing and not force:
        return "skip", f"[init] {target_db} already seeded for '{setup}' — skipping."
    other = [s for s in existing if s != setup]
    if other and not force:
        return "refuse", (
            f"[init] REFUSING to seed setup '{setup}' into '{target_db}': "
            f"it is already seeded for {other}. The atomic swap would "
            f"DISCARD all live data for {other}. If this setup change is "
            f"intentional, re-run with SEED_FORCE=1."
        )
    return "proceed", ""


async def run(setup: str) -> None:
    target_url = os.environ["SEED_TARGET_PG_URL"]
    redis_url = os.environ["SEED_TARGET_REDIS_URL"]
    # Escape hatch for the rare intentional re-seed / setup change. Set
    # SEED_FORCE=1 to allow swapping a fully-seeded DB to a *different*
    # setup (which discards the live data) or re-running the same setup.
    force = os.environ.get("SEED_FORCE", "").strip().lower() in {"1", "true", "yes"}

    target_db = urlparse(target_url).path.lstrip("/")
    if not target_db:
        raise SystemExit("SEED_TARGET_PG_URL must include a database path")
    staging_db = f"{target_db}_staging"
    admin_url = _swap_url(target_url, "/postgres")
    staging_url = _swap_url(target_url, f"/{staging_db}")

    # 1. Marker check on current target. The stock postgres image
    #    auto-creates POSTGRES_DB on first boot, so this normally
    #    succeeds; if the target doesn't exist yet, we just proceed.
    #
    #    Two guards here, both reading the `_glow_seed_complete` marker:
    #      (a) idempotency — already seeded for THIS setup ⇒ skip.
    #      (b) anti-downgrade — already seeded for a DIFFERENT setup ⇒
    #          refuse, because the swap below does a whole-DB
    #          `ALTER DATABASE RENAME` that would silently discard the
    #          live data. This is the class of bug that wiped a live
    #          `university` instance (28 seeded attempts + all academic
    #          data) when a re-seed ran with the default SEED_SETUP=fresh.
    #          SEED_FORCE=1 overrides for an intentional setup change.
    try:
        target_conn = await asyncpg.connect(target_url)
        try:
            existing = await _existing_setups(target_conn)
        finally:
            await target_conn.close()
        action, message = _seed_decision(
            setup, existing, force=force, target_db=target_db
        )
        if action == "skip":
            print(message)
            return
        if action == "refuse":
            raise SystemExit(message)
    except asyncpg.InvalidCatalogNameError:
        print(f"[init] target db '{target_db}' missing — will be created via swap.")

    print(
        f"[init] Seeding into staging '{staging_db}' "
        f"(target '{target_db}', setup '{setup}')"
    )

    # 2. Fresh staging DB.
    admin = await asyncpg.connect(admin_url)
    try:
        await _terminate(admin, staging_db)
        await admin.execute(f'DROP DATABASE IF EXISTS "{staging_db}"')
        await admin.execute(f'CREATE DATABASE "{staging_db}"')
    finally:
        await admin.close()

    # 3. Run seeds against staging. If this raises, staging is left
    #    behind for inspection (the next run drops + recreates it).
    await main_setup(
        setup=setup,
        target_pg_url=staging_url,
        target_redis_url=redis_url,
    )

    # 4. Stamp marker in staging.
    staging_conn = await asyncpg.connect(staging_url)
    try:
        await staging_conn.execute(MARKER_DDL)
        await staging_conn.execute(
            "INSERT INTO _glow_seed_complete (setup) VALUES ($1) "
            "ON CONFLICT (setup) DO UPDATE SET completed_at = now()",
            setup,
        )
    finally:
        await staging_conn.close()

    # 5. Atomic swap: rename target → _old, staging → target, drop _old.
    #    ALTER DATABASE RENAME requires the DB to have zero connections.
    print(f"[init] Swapping {staging_db} → {target_db}")
    old_db = f"{target_db}_old"
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{old_db}"')
        # Target may not exist if the auto-init step was skipped; tolerate.
        await _terminate(admin, target_db)
        try:
            await admin.execute(f'ALTER DATABASE "{target_db}" RENAME TO "{old_db}"')
        except asyncpg.InvalidCatalogNameError:
            pass  # target didn't exist — nothing to move aside
        await _terminate(admin, staging_db)
        await admin.execute(f'ALTER DATABASE "{staging_db}" RENAME TO "{target_db}"')
        await admin.execute(f'DROP DATABASE IF EXISTS "{old_db}"')
    finally:
        await admin.close()

    print(f"[init] Seed complete — '{target_db}' is live.")


def _cli() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument(
        "--setup",
        default=os.environ.get("SEED_SETUP", "fresh"),
        help="Setup name (env: SEED_SETUP).",
    )
    args = parser.parse_args()
    try:
        asyncio.run(run(args.setup))
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    _cli()
