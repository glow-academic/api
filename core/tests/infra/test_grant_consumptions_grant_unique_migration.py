"""I1 regression — the grant_consumptions grant-unique migration is self-healing.

The I1 migration (``20260611_add_grant_consumptions_grant_unique.sql``) adds
``grant_consumptions_entry_grant_uidx (grant_id) WHERE active`` — at most one
ACTIVE consumption per grant_id, the hard backstop for the emulation-grant
double-consume race (a single-use impersonation grant being replayed).

Like the soft-call terminal-unique migration, a bare ``CREATE UNIQUE INDEX`` on
an instance that already hit the race (duplicate active consumptions per
grant_id) would raise a unique violation, roll the whole file back (incl. its
``migrations.applied`` insert), and fail identically on every later deploy. The
migration prepends a dedup pass that keeps, per grant_id, the row the
``grant_consumptions_mv`` surfaces (WHERE active=true, latest created_at) and
deletes the rest, THEN creates the index. These run the real migration file
against the testcontainer DB seeded with duplicate active rows and assert: (1)
it applies with no unique violation, (2) the surviving row is the latest active.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio

_MIGRATION = (
    Path(__file__).resolve().parents[3]
    / "database"
    / "migrate"
    / "add"
    / "20260611_add_grant_consumptions_grant_unique.sql"
)

# Canonical definition from database/schema/indexes/entries/grant.sql — the
# backstop the live schema ships (and the migration recreates identically).
_CANONICAL_INDEX_SQL = (
    "CREATE UNIQUE INDEX IF NOT EXISTS grant_consumptions_entry_grant_uidx "
    "ON public.grant_consumptions_entry USING btree (grant_id) "
    "WHERE (active = true)"
)


async def _insert_consumption(conn, *, grant_id, active: bool = True):
    """Append one grant_consumptions row, bypassing the grant_id FK.

    The grant_id → grants_entry FK is irrelevant to the dedup-then-index
    behavior under test; the caller sets session_replication_role = replica so
    the FK trigger is bypassed for these synthetic rows (disposable container).
    """
    return await conn.fetchrow(
        """
        INSERT INTO grant_consumptions_entry (grant_id, active, mcp, generated)
        VALUES ($1, $2, false, true)
        RETURNING id, created_at
        """,
        grant_id,
        active,
    )


async def _drop_index_if_exists(conn) -> None:
    await conn.execute("DROP INDEX IF EXISTS grant_consumptions_entry_grant_uidx")


async def _active_rows(conn, grant_id):
    return await conn.fetch(
        """
        SELECT id, active, created_at
        FROM grant_consumptions_entry
        WHERE grant_id = $1 AND active = true
        ORDER BY created_at DESC, id DESC
        """,
        grant_id,
    )


async def _bypass_fks(conn) -> None:
    await conn.execute("SET session_replication_role = replica")


async def _restore_fks(conn) -> None:
    await conn.execute("SET session_replication_role = origin")


async def _restore_shared_db(conn, grant_id) -> None:
    """Restore the SHARED session DB (autocommit pool — state leaks)."""
    await conn.execute(
        "DELETE FROM grant_consumptions_entry WHERE grant_id = $1", grant_id
    )
    await conn.execute(_CANONICAL_INDEX_SQL)


async def test_migration_dedups_then_creates_index_on_dirty_instance(pool):
    """Seed duplicate ACTIVE consumptions (the double-consume aftermath) then
    run the real migration: it must dedup-then-create-the-index with NO
    unique violation."""
    migration_sql = _MIGRATION.read_text()
    grant_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM grant_consumptions_entry WHERE grant_id = $1", grant_id
        )

        # An inactive (soft) consumption (must survive — index only constrains
        # active rows) plus THREE active consumptions = the duplicates the
        # pre-fix double-consume race produced.
        await _bypass_fks(conn)
        await _insert_consumption(conn, grant_id=grant_id, active=False)
        first = await _insert_consumption(conn, grant_id=grant_id)
        second = await _insert_consumption(conn, grant_id=grant_id)
        latest = await _insert_consumption(conn, grant_id=grant_id)

        # Pre-condition: a bare CREATE UNIQUE INDEX would fail here (3 active).
        assert len(await _active_rows(conn, grant_id)) == 3

        # Run the actual migration file (origin session). Must NOT raise.
        await _restore_fks(conn)
        await conn.execute(migration_sql)

        survivors = await _active_rows(conn, grant_id)
        assert len(survivors) == 1, "dedup must collapse to one active row"

        # The kept row is the MV-canonical one: latest active by created_at/id.
        assert survivors[0]["id"] in {first["id"], second["id"], latest["id"]}
        assert survivors[0]["id"] == latest["id"], (
            "dedup must keep the MV-surfaced row (latest active consumption)"
        )

        # The inactive (soft) row is untouched.
        inactive = await conn.fetch(
            "SELECT id FROM grant_consumptions_entry "
            "WHERE grant_id = $1 AND active = false",
            grant_id,
        )
        assert len(inactive) == 1

        # The index is real: a second active insert now fails (the backstop).
        await _bypass_fks(conn)
        with pytest.raises(Exception) as exc_info:
            await _insert_consumption(conn, grant_id=grant_id)
        assert "grant_consumptions_entry_grant_uidx" in str(
            exc_info.value
        ) or "unique" in str(exc_info.value).lower()

        await _restore_fks(conn)
        await _restore_shared_db(conn, grant_id)


async def test_migration_idempotent_on_clean_instance(pool):
    """On a clean instance (one active consumption per grant_id) the dedup
    removes nothing and the index creates fine — re-running is a no-op."""
    migration_sql = _MIGRATION.read_text()
    grant_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM grant_consumptions_entry WHERE grant_id = $1", grant_id
        )

        await _bypass_fks(conn)
        only_active = await _insert_consumption(conn, grant_id=grant_id)

        await _restore_fks(conn)
        await conn.execute(migration_sql)
        # Re-run: IF NOT EXISTS index + dedup-of-nothing → no error.
        await conn.execute(migration_sql)

        survivors = await _active_rows(conn, grant_id)
        assert len(survivors) == 1
        assert survivors[0]["id"] == only_active["id"]

        await _restore_shared_db(conn, grant_id)
