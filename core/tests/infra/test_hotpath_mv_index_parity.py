# Ptest: regression — hot-path MV foreign-key index schema/migration parity.
"""Ptest regression — hot-path MV foreign-key index schema/migration parity.

The three hottest materialized-view reads each filter on a FOREIGN-KEY column
that originally had NO index (only the MV's PRIMARY-KEY column was indexed), so
every per-request / per-page read did a full MV seq scan + sort — the "box hangs
under load" profile. The accelerator indexes are:

* ``idx_sessions_mv_profile_created`` on ``sessions_mv`` (profile_id, session_created_at DESC)
  — ``search_sessions(profile_ids=[…])`` on EVERY authenticated request.
* ``idx_runs_mv_group_id`` on ``runs_mv`` (group_id, run_created_at)
  — ``search_runs(group_ids=[…])`` on every conversation/generation-history load.
* ``idx_attempt_mv_profile_created`` on ``attempt_mv`` (profile_id, attempt_created_at DESC)
  — ``search_attempts(profile_ids=[…])`` on every home/practice/dashboard/record page.

These were added to the dated add-migration
``20260614_add_hotpath_mv_fk_indexes.sql`` AND to the canonical schema
(``database/schema/indexes/views/{sessions_mv,runs_mv,attempt_mv}.sql`` + the
concatenated ``database/schema.sql``). Because a fresh deploy builds from the
schema (never ``migrate/add/`` — add migrations are skipped on first deploy), a
fresh-deploy instance would permanently lack any index that lives only in the
migration and would seq-scan these hot reads, while migrated instances had them.
This pins all paths together: the migration AND the canonical schema must define
all three indexes, so fresh and migrated databases match.

Mirrors ``test_operation_key_index_parity.py``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# core/tests/infra/<file> → repo root is three levels up from core/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DB = _REPO_ROOT / "database"

_MIGRATION = _DB / "migrate" / "add" / "20260614_add_hotpath_mv_fk_indexes.sql"

# The three hot-path indexes, with the MV each is built on.
_REQUIRED = {
    "idx_sessions_mv_profile_created": "sessions_mv",
    "idx_runs_mv_group_id": "runs_mv",
    "idx_attempt_mv_profile_created": "attempt_mv",
}


def _defines_index(sql: str, index_name: str, on_object: str) -> bool:
    """True if ``sql`` contains a CREATE [UNIQUE] INDEX [IF NOT EXISTS] for
    ``index_name`` on ``on_object`` (schema-qualified or not)."""
    pattern = re.compile(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?"
        + re.escape(index_name)
        + r"\b[\s\S]*?ON\s+(?:public\.)?"
        + re.escape(on_object)
        + r"\b",
        re.IGNORECASE,
    )
    return pattern.search(sql) is not None


def test_hotpath_migration_file_exists() -> None:
    """The dated add-migration that introduces the three indexes is present."""
    assert _MIGRATION.is_file(), f"missing hot-path index migration {_MIGRATION}"


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_hotpath_index_in_migration(index_name: str, on_object: str) -> None:
    """The incremental (migration) path defines all three indexes."""
    migration = _MIGRATION.read_text()
    assert _defines_index(migration, index_name, on_object), (
        f"{index_name} on {on_object} missing from the add-migration"
    )


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_hotpath_index_in_structured_schema(index_name: str, on_object: str) -> None:
    """The fresh path (structured database/schema/**) defines all three indexes,
    each in its MV's view-index file under schema/indexes/views/."""
    schema_file = _DB / "schema" / "indexes" / "views" / f"{on_object}.sql"
    sql = schema_file.read_text()
    assert _defines_index(sql, index_name, on_object), (
        f"{index_name} on {on_object} missing from {schema_file}"
    )


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_hotpath_index_in_concatenated_schema(index_name: str, on_object: str) -> None:
    """The canonical database/schema.sql (loaded by the schema-check CI and the
    fresh-deploy init swap) defines all three indexes — parity with the
    migration."""
    schema_sql = (_DB / "schema.sql").read_text()
    assert _defines_index(schema_sql, index_name, on_object), (
        f"{index_name} on {on_object} missing from database/schema.sql"
    )
