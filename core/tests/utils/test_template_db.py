"""Tests for template DB utility helpers."""

import pytest

from app.utils import template_db
from app.utils.template_db import compute_db_hash, get_admin_url


def test_get_admin_url_replaces_database_name():
    assert (
        get_admin_url("postgresql://user:pass@localhost:5432/appdb")
        == "postgresql://user:pass@localhost:5432/postgres"
    )


def test_compute_db_hash_changes_when_schema_changes(tmp_path):
    database_dir = tmp_path / "database"
    schema_dir = database_dir / "schema" / "tables"
    schema_dir.mkdir(parents=True)
    (schema_dir / "a.sql").write_text("CREATE TABLE a();", encoding="utf-8")

    first = compute_db_hash(database_dir)

    (schema_dir / "a.sql").write_text("CREATE TABLE a(id int);", encoding="utf-8")
    second = compute_db_hash(database_dir)

    assert len(first) == 16
    assert len(second) == 16
    assert first != second


def test_compute_db_hash_includes_relative_paths(tmp_path):
    database_dir = tmp_path / "database"
    schema_dir = database_dir / "schema" / "alpha"
    schema_dir.mkdir(parents=True)
    (schema_dir / "same.sql").write_text("CREATE TABLE a();", encoding="utf-8")

    first = compute_db_hash(database_dir)

    # Move to a different subdirectory — hash should change
    beta_dir = database_dir / "schema" / "beta"
    beta_dir.mkdir(parents=True)
    (beta_dir / "same.sql").write_text("CREATE TABLE a();", encoding="utf-8")
    (schema_dir / "same.sql").unlink()

    second = compute_db_hash(database_dir)

    assert first != second


class _FakeAdminConn:
    def __init__(
        self,
        *,
        fetchval_results: list[object | None] | None = None,
        fetch_results: list[list[dict[str, str]]] | None = None,
        execute_side_effects: list[Exception | None] | None = None,
        fail_create_once: bool = False,
    ) -> None:
        self.fetchval_results = list(fetchval_results or [])
        self.fetch_results = list(fetch_results or [])
        self.execute_side_effects = list(execute_side_effects or [])
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.fail_create_once = fail_create_once

    async def fetchval(self, query: str, *args: object) -> object | None:
        self.executed.append((query, args))
        if self.fetchval_results:
            return self.fetchval_results.pop(0)
        return None

    async def fetch(self, query: str, *args: object) -> list[dict[str, str]]:
        self.executed.append((query, args))
        if self.fetch_results:
            return self.fetch_results.pop(0)
        return []

    async def execute(self, query: str, *args: object) -> None:
        self.executed.append((query, args))
        if self.fail_create_once and 'CREATE DATABASE "test_glow_xyz"' in query:
            self.fail_create_once = False
            raise template_db.asyncpg.DuplicateDatabaseError("dup")
        if self.execute_side_effects:
            effect = self.execute_side_effects.pop(0)
            if effect is not None:
                raise effect


@pytest.mark.asyncio
async def test_template_exists_returns_true_when_database_exists():
    conn = _FakeAdminConn(fetchval_results=[1])

    assert await template_db.template_exists(conn, "template_glow_abc") is True


@pytest.mark.asyncio
async def test_clone_from_template_drops_existing_target_before_create():
    conn = _FakeAdminConn(fetchval_results=[1])

    await template_db.clone_from_template(conn, "template_glow_abc", "test_glow_xyz")

    executed_sql = [sql for sql, _args in conn.executed]
    assert any("DROP DATABASE IF EXISTS" in sql for sql in executed_sql)
    assert any(
        'CREATE DATABASE "test_glow_xyz" TEMPLATE "template_glow_abc"' in sql
        for sql in executed_sql
    )


@pytest.mark.asyncio
async def test_clone_from_template_retries_after_duplicate_database_race():
    conn = _FakeAdminConn(
        fetchval_results=[None, None],
        fail_create_once=True,
    )

    await template_db.clone_from_template(conn, "template_glow_abc", "test_glow_xyz")

    create_statements = [
        sql for sql, _args in conn.executed if 'CREATE DATABASE "test_glow_xyz"' in sql
    ]
    assert len(create_statements) == 2


@pytest.mark.asyncio
async def test_save_as_template_replaces_existing_template():
    conn = _FakeAdminConn(fetchval_results=[1])

    await template_db.save_as_template(conn, "build_glow_abc", "template_glow_abc")

    executed_sql = [sql for sql, _args in conn.executed]
    assert any(
        'ALTER DATABASE "template_glow_abc" IS_TEMPLATE false' in sql
        for sql in executed_sql
    )
    assert any('DROP DATABASE "template_glow_abc"' in sql for sql in executed_sql)
    assert any(
        'CREATE DATABASE "template_glow_abc" TEMPLATE "build_glow_abc"' in sql
        for sql in executed_sql
    )
    assert any(
        'ALTER DATABASE "template_glow_abc" IS_TEMPLATE true' in sql
        for sql in executed_sql
    )


@pytest.mark.asyncio
async def test_create_fresh_db_drops_existing_before_create():
    conn = _FakeAdminConn(fetchval_results=[1])

    await template_db.create_fresh_db(conn, "test_glow_abc")

    executed_sql = [sql for sql, _args in conn.executed]
    assert any("pg_terminate_backend" in sql for sql in executed_sql)
    assert any('DROP DATABASE IF EXISTS "test_glow_abc"' in sql for sql in executed_sql)
    assert any('CREATE DATABASE "test_glow_abc"' in sql for sql in executed_sql)


@pytest.mark.asyncio
async def test_cleanup_old_templates_preserves_requested_template_and_cleans_stale_dbs():
    conn = _FakeAdminConn(
        fetch_results=[
            [
                {"datname": "template_glow_newest"},
                {"datname": "template_glow_keep"},
                {"datname": "template_glow_drop"},
            ],
            [{"datname": "build_glow_tmp"}],
            [{"datname": "test_glow_tmp"}],
        ]
    )

    await template_db.cleanup_old_templates(
        conn,
        keep_count=1,
        preserve="template_glow_keep",
    )

    executed_sql = [sql for sql, _args in conn.executed]
    assert not any('DROP DATABASE "template_glow_keep"' in sql for sql in executed_sql)
    assert any('DROP DATABASE "template_glow_drop"' in sql for sql in executed_sql)
    assert any('DROP DATABASE "build_glow_tmp"' in sql for sql in executed_sql)
    assert any('DROP DATABASE "test_glow_tmp"' in sql for sql in executed_sql)
