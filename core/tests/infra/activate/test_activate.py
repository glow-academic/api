"""Tests for activate_rows helper."""

import pytest

from app.infra.activate.activate import activate_rows
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


async def test_activate_rows_sets_active_true_and_returns_ids(conn, redis_client):
    first = await create_name(conn, "inactive-a", redis_client, soft=True)
    second = await create_name(conn, "inactive-b", redis_client, soft=True)
    untouched = await create_name(conn, "still-inactive", redis_client, soft=True)

    result = await activate_rows(
        conn,
        table="names_resource",
        ids=[first.id, second.id],
    )

    assert set(result) == {first.id, second.id}

    rows = await conn.fetch(
        "SELECT id, active FROM names_resource WHERE id = ANY($1)",
        [first.id, second.id, untouched.id],
    )
    active_by_id = {row["id"]: row["active"] for row in rows}
    assert active_by_id[first.id] is True
    assert active_by_id[second.id] is True
    assert active_by_id[untouched.id] is False


async def test_activate_rows_returns_empty_list_for_no_ids(conn):
    assert await activate_rows(conn, table="names_resource", ids=[]) == []
