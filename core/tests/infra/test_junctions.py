"""Tests for infra.junctions — reusable junction upsert/insert helpers.

Uses temporary tables as an isolated test bed so there is no dependency
on any real artifact/resource tables.
"""

import pytest

from app.infra.junctions import (
    insert_multi,
    insert_single,
    upsert_multi,
    upsert_single,
)

pytestmark = pytest.mark.asyncio

OWNER_COL = "owner_id"
RESOURCE_COL = "resource_id"
TABLE = "_test_junction"
CONSTRAINT = "_test_junction_pkey"


async def _setup_tables(conn):
    """Create temporary tables that mimic the junction pattern."""
    await conn.execute(
        "CREATE TEMPORARY TABLE IF NOT EXISTS _test_owner ("
        "  id uuid PRIMARY KEY DEFAULT gen_random_uuid()"
        ")"
    )
    await conn.execute(
        "CREATE TEMPORARY TABLE IF NOT EXISTS _test_resource ("
        "  id uuid PRIMARY KEY DEFAULT gen_random_uuid()"
        ")"
    )
    await conn.execute(
        "CREATE TEMPORARY TABLE IF NOT EXISTS _test_junction ("
        "  owner_id uuid NOT NULL REFERENCES _test_owner(id),"
        "  resource_id uuid NOT NULL REFERENCES _test_resource(id),"
        "  active boolean NOT NULL DEFAULT true,"
        "  created_at timestamptz NOT NULL DEFAULT now(),"
        "  generated boolean NOT NULL DEFAULT false,"
        "  mcp boolean NOT NULL DEFAULT false,"
        "  CONSTRAINT _test_junction_pkey PRIMARY KEY (owner_id, resource_id)"
        ")"
    )


async def _make_owner(conn):
    return await conn.fetchval("INSERT INTO _test_owner DEFAULT VALUES RETURNING id")


async def _make_resource(conn):
    return await conn.fetchval("INSERT INTO _test_resource DEFAULT VALUES RETURNING id")


async def _active_ids(conn, owner_id):
    rows = await conn.fetch(
        f"SELECT {RESOURCE_COL} FROM {TABLE} WHERE {OWNER_COL} = $1 AND active = true",
        owner_id,
    )
    return {r[RESOURCE_COL] for r in rows}


# ---------------------------------------------------------------------------
# insert_single
# ---------------------------------------------------------------------------


async def test_insert_single(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    rid = await _make_resource(conn)

    await insert_single(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_id=rid,
    )

    assert await _active_ids(conn, oid) == {rid}


# ---------------------------------------------------------------------------
# insert_multi
# ---------------------------------------------------------------------------


async def test_insert_multi(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)
    r2 = await _make_resource(conn)

    await insert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1, r2],
    )

    assert await _active_ids(conn, oid) == {r1, r2}


async def test_insert_multi_empty_is_noop(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)

    await insert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[],
    )

    assert await _active_ids(conn, oid) == set()


# ---------------------------------------------------------------------------
# upsert_single — replace
# ---------------------------------------------------------------------------


async def test_upsert_single_replaces_old(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)
    r2 = await _make_resource(conn)

    await insert_single(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_id=r1,
    )

    await upsert_single(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_id=r2,
        constraint=CONSTRAINT,
    )

    assert await _active_ids(conn, oid) == {r2}

    # Old row deactivated, not deleted
    old = await conn.fetchval(
        f"SELECT active FROM {TABLE} WHERE {OWNER_COL} = $1 AND {RESOURCE_COL} = $2",
        oid,
        r1,
    )
    assert old is False


async def test_upsert_single_keeps_same(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)

    await insert_single(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_id=r1,
    )

    await upsert_single(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_id=r1,
        constraint=CONSTRAINT,
    )

    assert await _active_ids(conn, oid) == {r1}


# ---------------------------------------------------------------------------
# upsert_multi — add, remove, keep
# ---------------------------------------------------------------------------


async def test_upsert_multi_adds_new(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)
    r2 = await _make_resource(conn)

    await insert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1],
    )

    await upsert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1, r2],
        constraint=CONSTRAINT,
    )

    assert await _active_ids(conn, oid) == {r1, r2}


async def test_upsert_multi_removes_old(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)
    r2 = await _make_resource(conn)

    await insert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1, r2],
    )

    await upsert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1],
        constraint=CONSTRAINT,
    )

    assert await _active_ids(conn, oid) == {r1}

    r2_active = await conn.fetchval(
        f"SELECT active FROM {TABLE} WHERE {OWNER_COL} = $1 AND {RESOURCE_COL} = $2",
        oid,
        r2,
    )
    assert r2_active is False


async def test_upsert_multi_clears_all(conn):
    await _setup_tables(conn)
    oid = await _make_owner(conn)
    r1 = await _make_resource(conn)

    await insert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[r1],
    )

    await upsert_multi(
        conn,
        table=TABLE,
        owner_col=OWNER_COL,
        owner_id=oid,
        resource_col=RESOURCE_COL,
        resource_ids=[],
        constraint=CONSTRAINT,
    )

    assert await _active_ids(conn, oid) == set()
