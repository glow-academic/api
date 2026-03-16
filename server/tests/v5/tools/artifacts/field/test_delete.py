"""Tests for delete_fields — black-box using tool functions only."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.field.create import create_field
from app.tools.artifacts.field.delete import delete_fields
from app.tools.artifacts.field.get import get_fields
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_hard_delete_single(conn, redis_client):
    name = await create_name(conn, f"del-{_u()}", redis_client)
    p = await create_field(conn, name_id=name.id)
    result = await delete_fields(conn, [p.id])
    assert p.id in result.deleted_ids
    got = await get_fields(conn, [p.id], active=None)
    assert len(got) == 0


async def test_hard_delete_multiple(conn, redis_client):
    ids = []
    for _ in range(3):
        name = await create_name(conn, f"del-{_u()}", redis_client)
        p = await create_field(conn, name_id=name.id)
        ids.append(p.id)
    result = await delete_fields(conn, ids)
    assert set(result.deleted_ids) == set(ids)
    got = await get_fields(conn, ids)
    assert len(got) == 0


async def test_hard_delete_nonexistent(conn, redis_client):
    fake_id = nonexistent_id()
    result = await delete_fields(conn, [fake_id])
    assert result.deleted_ids == []


async def test_hard_delete_empty_list(conn, redis_client):
    result = await delete_fields(conn, [])
    assert result.deleted_ids == []


async def test_soft_delete_sets_inactive(conn, redis_client):
    name = await create_name(conn, f"soft-{_u()}", redis_client)
    p = await create_field(conn, name_id=name.id)
    result = await delete_fields(conn, [p.id], soft=True)
    assert p.id in result.deleted_ids
    got = await get_fields(conn, [p.id], active=None)
    assert len(got) == 1
    assert got[0].active is False


async def test_soft_delete_recoverable(conn, redis_client):
    name = await create_name(conn, f"recover-{_u()}", redis_client)
    p = await create_field(conn, name_id=name.id)
    await delete_fields(conn, [p.id], soft=True)
    row = await conn.fetchrow(
        "SELECT id, active FROM field_artifact WHERE id = $1", p.id
    )
    assert row is not None
    assert row["active"] is False


async def test_hard_delete_cascades_junctions(conn, redis_client):
    name = await create_name(conn, f"cascade-{_u()}", redis_client)
    p = await create_field(conn, name_id=name.id)
    await delete_fields(conn, [p.id])
    row = await conn.fetchrow(
        "SELECT 1 FROM field_names_junction WHERE field_id = $1", p.id
    )
    assert row is None
