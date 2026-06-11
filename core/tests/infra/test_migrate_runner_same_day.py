"""Regression — the migrate runner no longer silently skips a same-day dated
migration.

For DATED filenames (``YYYYMMDD_description.sql``) the old runner set
``number=0`` for every file and deduped on the UNIQUE ``(version, number,
type)`` key. So TWO migrations sharing a date both mapped to ``(YYYYMMDD, 0,
add)`` — once the first landed, every other same-day file matched the
already-applied row and was skipped FOREVER. That is exactly how
``20260611_add_grant_consumptions_grant_unique.sql`` got silently dropped on
deploy after ``20260611_add_soft_calls_terminal_unique.sql`` (same date) had
already been recorded at ``(20260611, 0)``.

The fix: dedup on the migration's stable identity — its ``name`` (filename) —
and hand same-day dated files DISTINCT numbers (the smallest free ordinal for
that ``(version, type)``). This keeps already-recorded rows untouched
(backward-compatible) while letting never-applied same-day files land.

These tests drive the REAL ``database.scripts.migrate._apply`` against the test
DB (a temp migrate root for the synthetic cases, the real 20260611 files for the
grant-after-soft_calls simulation).
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

import pytest

from database.scripts import migrate

pytestmark = pytest.mark.asyncio

_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_ADD = _REPO_ROOT / "database" / "migrate" / "add"
_GRANT_FILE = "20260611_add_grant_consumptions_grant_unique.sql"
_SOFT_CALLS_FILE = "20260611_add_soft_calls_terminal_unique.sql"


def _point_runner_at_test_db(monkeypatch) -> None:
    """Make ``migrate._connect`` reach the test DB via the DB_* env vars."""
    from app.utils.test_db import get_test_db_url

    dsn = get_test_db_url()
    assert dsn, "test DB url unavailable — did initialize_test_db run?"
    p = urlparse(dsn)
    monkeypatch.setenv("DB_USER", p.username or "")
    monkeypatch.setenv("DB_PASSWORD", p.password or "")
    monkeypatch.setenv("DB_HOST", p.hostname or "localhost")
    monkeypatch.setenv("DB_PORT", str(p.port or 5432))
    monkeypatch.setenv("DB_NAME", (p.path or "/").lstrip("/"))


def _write_migrate_root(monkeypatch, tmp_path: Path, files: dict[str, str]) -> None:
    """Lay out a throwaway ``add/`` migrate root and point the runner at it."""
    add_dir = tmp_path / "add"
    add_dir.mkdir()
    for name, sql in files.items():
        (add_dir / name).write_text(sql)
    monkeypatch.setattr(migrate, "_MIGRATE_ROOT", tmp_path)


async def _applied_rows(conn, version: str):
    return await conn.fetch(
        """
        SELECT number, name FROM migrations.applied
        WHERE version=$1 AND type='add'
        ORDER BY number
        """,
        version,
    )


async def test_two_same_day_dated_migrations_both_apply(pool, monkeypatch, tmp_path):
    """Two same-day dated files → BOTH apply, recorded with DISTINCT numbers."""
    version = "29990101"
    first = f"{version}_aaa_first.sql"
    second = f"{version}_bbb_second.sql"
    _point_runner_at_test_db(monkeypatch)
    _write_migrate_root(
        monkeypatch,
        tmp_path,
        {
            first: "CREATE TABLE IF NOT EXISTS public.migtest_aaa (id int);",
            second: "CREATE TABLE IF NOT EXISTS public.migtest_bbb (id int);",
        },
    )

    # _apply creates the migrations schema/table itself (_ensure_table); the
    # synthetic version is unique so there is nothing to pre-clean.
    try:
        await migrate._apply("add")
        async with pool.acquire() as conn:
            rows = await _applied_rows(conn, version)
            assert [r["name"] for r in rows] == [first, second]
            # distinct, deterministic numbers
            assert [r["number"] for r in rows] == [0, 1]
            # both objects really got created
            for tbl in ("migtest_aaa", "migtest_bbb"):
                assert await conn.fetchval(
                    "SELECT to_regclass($1)", f"public.{tbl}"
                ) is not None
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM migrations.applied WHERE version=$1", version
            )
            await conn.execute("DROP TABLE IF EXISTS public.migtest_aaa")
            await conn.execute("DROP TABLE IF EXISTS public.migtest_bbb")


async def test_already_applied_same_day_row_is_untouched(pool, monkeypatch, tmp_path):
    """An already-recorded same-day file keeps its number; the new same-day file
    is no longer skipped and lands at the next free number."""
    version = "29990202"
    first = f"{version}_aaa_first.sql"
    second = f"{version}_bbb_second.sql"
    _point_runner_at_test_db(monkeypatch)
    _write_migrate_root(
        monkeypatch,
        tmp_path,
        {
            first: "CREATE TABLE IF NOT EXISTS public.migtest_c1 (id int);",
            second: "CREATE TABLE IF NOT EXISTS public.migtest_c2 (id int);",
        },
    )

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS migrations")
        await migrate._ensure_table(conn)
        # Seed the FIRST file as already applied at number=0 (the historical key).
        await conn.execute(
            "DELETE FROM migrations.applied WHERE version=$1", version
        )
        await conn.execute(
            "INSERT INTO migrations.applied (version, number, type, name) "
            "VALUES ($1, 0, 'add', $2)",
            version, first,
        )
    try:
        await migrate._apply("add")
        async with pool.acquire() as conn:
            rows = await _applied_rows(conn, version)
            # first row unchanged (still 0), second landed at 1 — not skipped.
            assert [(r["number"], r["name"]) for r in rows] == [
                (0, first),
                (1, second),
            ]
            # first file was skipped → its table never created; second created.
            assert await conn.fetchval(
                "SELECT to_regclass('public.migtest_c1')"
            ) is None
            assert await conn.fetchval(
                "SELECT to_regclass('public.migtest_c2')"
            ) is not None
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM migrations.applied WHERE version=$1", version
            )
            await conn.execute("DROP TABLE IF EXISTS public.migtest_c2")


async def test_grant_migration_applies_after_soft_calls(pool, monkeypatch, tmp_path):
    """The real incident: soft_calls (20260611) already recorded at number=0 →
    the same-day grant migration must now still apply (index created + recorded),
    and the soft_calls row stays untouched."""
    version = "20260611"
    _point_runner_at_test_db(monkeypatch)
    # Only the two real same-day files, copied into an isolated root.
    _write_migrate_root(
        monkeypatch,
        tmp_path,
        {
            _GRANT_FILE: (_REAL_ADD / _GRANT_FILE).read_text(),
            _SOFT_CALLS_FILE: (_REAL_ADD / _SOFT_CALLS_FILE).read_text(),
        },
    )

    async with pool.acquire() as conn:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS migrations")
        await migrate._ensure_table(conn)
        await conn.execute(
            "DELETE FROM migrations.applied WHERE version=$1", version
        )
        # Simulate prod: soft_calls applied, recorded at the (date, 0) slot.
        await conn.execute(
            "INSERT INTO migrations.applied (version, number, type, name) "
            "VALUES ($1, 0, 'add', $2)",
            version, _SOFT_CALLS_FILE,
        )
        # Simulate the missing index that the skip left behind.
        await conn.execute(
            "DROP INDEX IF EXISTS grant_consumptions_entry_grant_uidx"
        )
        assert await conn.fetchval(
            "SELECT to_regclass('public.grant_consumptions_entry_grant_uidx')"
        ) is None

    try:
        await migrate._apply("add")
        async with pool.acquire() as conn:
            # The grant index now exists.
            assert await conn.fetchval(
                "SELECT to_regclass('public.grant_consumptions_entry_grant_uidx')"
            ) is not None
            rows = await _applied_rows(conn, version)
            by_name = {r["name"]: r["number"] for r in rows}
            # soft_calls untouched at 0; grant recorded at the next free slot.
            assert by_name[_SOFT_CALLS_FILE] == 0
            assert _GRANT_FILE in by_name
            assert by_name[_GRANT_FILE] == 1
            # soft_calls not duplicated (skipped by name, not re-applied).
            assert sum(1 for r in rows if r["name"] == _SOFT_CALLS_FILE) == 1
    finally:
        async with pool.acquire() as conn:
            await conn.execute(
                "DELETE FROM migrations.applied WHERE version=$1", version
            )
            # leave the canonical index in place (matches the loaded schema).
