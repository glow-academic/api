"""C1-B regression — the completion terminal-unique migration is self-healing.

``20260611_add_completion_terminal_unique.sql`` adds a UNIQUE(parent_fk)
constraint to each completion-entry sibling (test/file/image/video/audio/text/
upload/test_invocation_completion) — at most one completion row per parent, the
hard backstop behind the ON CONFLICT idempotency guard in each create.py.

A bare ADD CONSTRAINT UNIQUE would raise a unique violation on exactly the
instances that hit the pre-fix duplicate-completion bug (the ones with >1 row
per parent), rolling the whole file (incl. its ``migrations.applied`` insert)
back and failing identically on every later deploy. The migration prepends a
dedup pass that keeps, per parent, the row the *_completion_mv would surface
(active first, then latest created_at, then id) and deletes the rest, THEN adds
the constraint.

These run the real migration file against the testcontainer DB. The
representative table is ``test_invocation_completion_entry`` (invocation_id);
the other seven tables share the identical dedup-then-constraint shape. We test
against the autocommitting ``pool`` fixture (NOT the rollback-wrapped ``conn``)
and restore state afterward, mirroring the soft_calls dedup migration test.
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
    / "20260611_add_completion_terminal_unique.sql"
)

_CONSTRAINT = "test_invocation_completion_entry_invocation_unique"
_TABLE = "test_invocation_completion_entry"


async def _insert(conn, *, invocation_id, active: bool = True):
    """Append one completion row, bypassing the FK trigger (synthetic seed)."""
    return await conn.fetchrow(
        f"""
        INSERT INTO {_TABLE}
            (invocation_id, call_id, stop, error, message, active, mcp, generated)
        VALUES ($1, $2, false, false, '', $3, false, true)
        RETURNING id, created_at
        """,
        invocation_id,
        uuid4(),
        active,
    )


async def _drop_constraint(conn) -> None:
    await conn.execute(
        f"ALTER TABLE public.{_TABLE} DROP CONSTRAINT IF EXISTS {_CONSTRAINT}"
    )


async def _restore_constraint(conn) -> None:
    """Re-add the canonical constraint the live schema ships, so the shared
    autocommit DB is left exactly as the schema load created it."""
    await conn.execute(
        f"""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{_CONSTRAINT}') THEN
                ALTER TABLE public.{_TABLE}
                    ADD CONSTRAINT {_CONSTRAINT} UNIQUE (invocation_id);
            END IF;
        END $$;
        """
    )


async def _rows(conn, invocation_id):
    return await conn.fetch(
        f"SELECT id, active, created_at FROM {_TABLE} "
        "WHERE invocation_id = $1 ORDER BY created_at DESC, id DESC",
        invocation_id,
    )


async def test_migration_dedups_then_adds_constraint_on_dirty_instance(pool):
    migration_sql = _MIGRATION.read_text()
    invocation_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_constraint(conn)
        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)

        await conn.execute("SET session_replication_role = replica")
        first = await _insert(conn, invocation_id=invocation_id)
        await _insert(conn, invocation_id=invocation_id)
        latest = await _insert(conn, invocation_id=invocation_id)
        # Pre-condition: a bare ADD CONSTRAINT would fail here (3 rows).
        assert len(await _rows(conn, invocation_id)) == 3
        await conn.execute("SET session_replication_role = origin")

        # Run the real migration — must NOT raise (dedup runs first).
        await conn.execute(migration_sql)

        survivors = await _rows(conn, invocation_id)
        assert len(survivors) == 1, "dedup must collapse to one row"
        # MV-canonical kept row: latest active (all active + same → last inserted).
        assert survivors[0]["id"] in {first["id"], latest["id"]}
        assert survivors[0]["id"] == latest["id"]

        # The constraint is real: a second row now fails.
        await conn.execute("SET session_replication_role = replica")
        with pytest.raises(Exception) as exc:
            await _insert(conn, invocation_id=invocation_id)
        assert "unique" in str(exc.value).lower() or _CONSTRAINT in str(exc.value)
        await conn.execute("SET session_replication_role = origin")

        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)
        await _restore_constraint(conn)


async def test_migration_keeps_active_over_inactive(pool):
    migration_sql = _MIGRATION.read_text()
    invocation_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_constraint(conn)
        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)

        await conn.execute("SET session_replication_role = replica")
        active_row = await _insert(conn, invocation_id=invocation_id, active=True)
        await _insert(conn, invocation_id=invocation_id, active=False)
        await conn.execute("SET session_replication_role = origin")

        await conn.execute(migration_sql)

        survivors = await _rows(conn, invocation_id)
        assert len(survivors) == 1
        assert survivors[0]["id"] == active_row["id"], (
            "dedup must keep the active row (what the MV surfaces)"
        )

        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)
        await _restore_constraint(conn)


async def test_migration_idempotent_on_clean_instance(pool):
    migration_sql = _MIGRATION.read_text()
    invocation_id = uuid4()

    async with pool.acquire() as conn:
        await _drop_constraint(conn)
        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)

        await conn.execute("SET session_replication_role = replica")
        only_row = await _insert(conn, invocation_id=invocation_id)
        await conn.execute("SET session_replication_role = origin")

        # First apply + re-apply: dedup-of-nothing + guarded ADD CONSTRAINT → no error.
        await conn.execute(migration_sql)
        await conn.execute(migration_sql)

        survivors = await _rows(conn, invocation_id)
        assert len(survivors) == 1
        assert survivors[0]["id"] == only_row["id"]

        await conn.execute(f"DELETE FROM {_TABLE} WHERE invocation_id = $1", invocation_id)
        await _restore_constraint(conn)
