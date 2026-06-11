"""DEP2 regression — operation_key index schema/migration parity.

The idempotency replay gate (``search_calls(operation_keys=[...])`` →
``calls_mv`` lookup) is a hot read on the replay path. Its lookup indexes
(``idx_calls_entry_operation_key`` on ``calls_entry`` and
``idx_calls_mv_operation_key`` on ``calls_mv``) originally lived ONLY in the
dated add-migration ``20260520_add_operation_key_indexes.sql`` and were absent
from the canonical schema (``database/schema/**`` + the concatenated
``database/schema.sql``).

Because a fresh deploy builds from the schema (never ``migrate/add/`` — add
migrations are skipped on first deploy), every first-deploy instance
permanently lacked these indexes and did a seq scan on the replay gate, while
pre-existing/migrated instances had them. This pins the two paths together:
both the migration AND the canonical schema must define both indexes, so fresh
and migrated databases match.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# core/tests/infra/<file> → repo root is three levels up from core/.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DB = _REPO_ROOT / "database"

# The two indexes the replay gate depends on, with the object each is built on.
_REQUIRED = {
    "idx_calls_entry_operation_key": "calls_entry",
    "idx_calls_mv_operation_key": "calls_mv",
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


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_operation_key_index_in_migration(index_name: str, on_object: str) -> None:
    """The incremental (migration) path defines both indexes."""
    migration = (
        _DB / "migrate" / "add" / "20260520_add_operation_key_indexes.sql"
    ).read_text()
    assert _defines_index(migration, index_name, on_object), (
        f"{index_name} on {on_object} missing from the add-migration"
    )


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_operation_key_index_in_structured_schema(
    index_name: str, on_object: str
) -> None:
    """The fresh path (structured database/schema/**) defines both indexes,
    each in its proper subfolder (entries/ for the base table, views/ for the
    MV)."""
    subdir = "views" if on_object.endswith("_mv") else "entries"
    # calls base-table indexes live in calls.sql; MV indexes in calls_mv.sql.
    fname = "calls_mv.sql" if on_object.endswith("_mv") else "calls.sql"
    schema_file = _DB / "schema" / "indexes" / subdir / fname
    sql = schema_file.read_text()
    assert _defines_index(sql, index_name, on_object), (
        f"{index_name} on {on_object} missing from {schema_file}"
    )


@pytest.mark.parametrize(("index_name", "on_object"), list(_REQUIRED.items()))
def test_operation_key_index_in_concatenated_schema(
    index_name: str, on_object: str
) -> None:
    """The canonical database/schema.sql (loaded by the schema-check CI and the
    fresh-deploy init swap) defines both indexes — parity with the migration."""
    schema_sql = (_DB / "schema.sql").read_text()
    assert _defines_index(schema_sql, index_name, on_object), (
        f"{index_name} on {on_object} missing from database/schema.sql"
    )
