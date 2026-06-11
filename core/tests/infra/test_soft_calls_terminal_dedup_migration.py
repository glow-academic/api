"""DEP3 regression — the soft_calls terminal-unique migration is self-healing.

The #338 migration (``20260611_add_soft_calls_terminal_unique.sql``) adds
``soft_calls_entry_terminal_call_uidx (call_id) WHERE status <> 'pending'`` —
at most one terminal ledger row per call_id, the hard backstop for the A3
double-ack race.

The bug (DEP3): the migration originally did a bare ``CREATE UNIQUE INDEX``
with no dedup. On exactly the instances that hit the pre-fix race — the ones
that ALREADY have duplicate terminal rows — the CREATE raises a unique
violation, the runner rolls the whole file (incl. its ``migrations.applied``
insert) back, and it fails identically on every later deploy: the backstop
never lands where it's needed.

The fix prepends a dedup pass that keeps, per call_id, the row the
``soft_calls_mv`` would surface (DISTINCT ON (call_id) WHERE active=true ORDER
BY created_at DESC) and deletes the rest, THEN creates the index. These run the
real migration file against a testcontainer DB seeded with duplicate terminal
rows and assert: (1) it applies with no unique violation, (2) the surviving row
per call_id is the MV-canonical one.
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
    / "20260611_add_soft_calls_terminal_unique.sql"
)


async def _insert_soft_call(
    conn,
    *,
    call_id,
    status: str,
    active: bool = True,
):
    """Append one soft_calls ledger row, returning (id, created_at).

    The soft_calls_entry.call_id → calls_entry FK is irrelevant to the
    dedup-then-index behavior under test, and building the full
    calls→runs→groups parent chain would be pure noise. We seed under
    ``session_replication_role = replica`` (set by the caller) so the FK
    trigger is bypassed for these synthetic rows; this is a disposable
    per-test container. created_at advances per autocommit statement; the
    uuidv7 id is a monotonic tie-break either way.
    """
    return await conn.fetchrow(
        """
        INSERT INTO soft_calls_entry
            (call_id, artifact, operation, status, artifact_id, active,
             mcp, generated, eval)
        VALUES ($1, 'attempt', 'complete', $2, $3, $4, false, true, false)
        RETURNING id, created_at
        """,
        call_id,
        status,
        uuid4(),
        active,
    )


async def _drop_index_if_exists(conn) -> None:
    await conn.execute(
        "DROP INDEX IF EXISTS soft_calls_entry_terminal_call_uidx"
    )


async def _bypass_fks(conn) -> None:
    """Bypass FK triggers for synthetic seed rows (see _insert_soft_call)."""
    await conn.execute("SET session_replication_role = replica")


async def _restore_fks(conn) -> None:
    await conn.execute("SET session_replication_role = origin")


async def _terminal_rows(conn, call_id):
    return await conn.fetch(
        """
        SELECT id, status, active, created_at
        FROM soft_calls_entry
        WHERE call_id = $1 AND status <> 'pending'
        ORDER BY created_at DESC, id DESC
        """,
        call_id,
    )


async def test_migration_dedups_then_creates_index_on_dirty_instance(pool):
    """Seed duplicate terminal rows (the A3 race aftermath) then run the real
    migration: it must dedup-then-create-the-index with NO unique violation."""
    migration_sql = _MIGRATION.read_text()
    call_id = uuid4()

    async with pool.acquire() as conn:
        # Ensure a clean slate (the index may exist from a prior run / schema).
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )

        # One pending row (must survive — the index only constrains terminals)
        # plus THREE terminal rows for the same call_id = the duplicates the
        # pre-fix double-ack race produced.
        await _bypass_fks(conn)
        await _insert_soft_call(conn, call_id=call_id, status="pending")
        first = await _insert_soft_call(conn, call_id=call_id, status="accepted")
        second = await _insert_soft_call(conn, call_id=call_id, status="accepted")
        latest = await _insert_soft_call(conn, call_id=call_id, status="accepted")

        # Pre-condition: a bare CREATE UNIQUE INDEX would fail here (3 terminals).
        assert len(await _terminal_rows(conn, call_id)) == 3

        # Run the actual migration file as a normal (origin) session. Must NOT
        # raise UniqueViolationError — the dedup pass runs first.
        await _restore_fks(conn)
        await conn.execute(migration_sql)

        # Index now exists and holds exactly one terminal row for the call_id.
        survivors = await _terminal_rows(conn, call_id)
        assert len(survivors) == 1, "dedup must collapse to one terminal row"

        # The kept row is the MV-canonical one: among active terminal rows, the
        # latest by created_at (then id). All three are active + same status, so
        # the last-inserted (latest created_at / highest uuidv7 id) wins.
        kept_id = survivors[0]["id"]
        assert kept_id in {first["id"], second["id"], latest["id"]}
        assert kept_id == latest["id"], (
            "dedup must keep the MV-surfaced row (latest active terminal)"
        )

        # The pending row is untouched.
        pending = await conn.fetch(
            "SELECT id FROM soft_calls_entry "
            "WHERE call_id = $1 AND status = 'pending'",
            call_id,
        )
        assert len(pending) == 1

        # The index is real: a second terminal insert now fails (the backstop).
        # Bypass FKs so the ONLY thing that can reject it is the unique index.
        await _bypass_fks(conn)
        with pytest.raises(Exception) as exc_info:
            await _insert_soft_call(conn, call_id=call_id, status="rejected")
        assert "soft_calls_entry_terminal_call_uidx" in str(
            exc_info.value
        ) or "unique" in str(exc_info.value).lower()

        # cleanup
        await _restore_fks(conn)
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )


async def test_migration_keeps_active_terminal_over_inactive(pool):
    """The MV reads WHERE active=true; the dedup must prefer an active terminal
    row over an inactive one even if the inactive row is newer-by-id."""
    migration_sql = _MIGRATION.read_text()
    call_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )

        # Insert an ACTIVE terminal first, then an INACTIVE terminal (higher
        # uuidv7 id / later created_at). The MV would surface the active one;
        # the dedup (ORDER BY active DESC, created_at DESC, id DESC) must too.
        await _bypass_fks(conn)
        active_row = await _insert_soft_call(
            conn, call_id=call_id, status="accepted", active=True
        )
        await _insert_soft_call(
            conn, call_id=call_id, status="rejected", active=False
        )

        await _restore_fks(conn)
        await conn.execute(migration_sql)

        survivors = await _terminal_rows(conn, call_id)
        assert len(survivors) == 1
        assert survivors[0]["id"] == active_row["id"], (
            "dedup must keep the active terminal row (what the MV surfaces)"
        )

        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )


async def test_migration_idempotent_on_clean_instance(pool):
    """On a clean instance (one terminal row per call_id) the dedup removes
    nothing and the index creates fine — and re-running is a no-op."""
    migration_sql = _MIGRATION.read_text()
    call_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )

        await _bypass_fks(conn)
        await _insert_soft_call(conn, call_id=call_id, status="pending")
        only_terminal = await _insert_soft_call(
            conn, call_id=call_id, status="accepted"
        )

        await _restore_fks(conn)
        await conn.execute(migration_sql)
        # Re-run: IF NOT EXISTS index + dedup-of-nothing → no error.
        await conn.execute(migration_sql)

        survivors = await _terminal_rows(conn, call_id)
        assert len(survivors) == 1
        assert survivors[0]["id"] == only_terminal["id"]

        await _drop_index_if_exists(conn)
        await conn.execute(
            "DELETE FROM soft_calls_entry WHERE call_id = $1", call_id
        )
