"""Tests for update_field — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.field.create import create_field
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.field.update import update_field
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u() -> str:
    return unique_tag()


async def _create_with_junctions(conn, redis_client):
    """Create a field with single + multi junctions for update tests."""
    n = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    result = await create_field(
        conn, name_id=n.id, description_id=desc.id, department_ids=[d1.id, d2.id]
    )
    return result.id, n.id, desc.id, d1.id, d2.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_updates_mcp(conn, redis_client):
    result = await create_field(conn)
    await update_field(conn, result.id, mcp=True)

    items = await get_fields(conn, [result.id])
    assert items[0].mcp is True


async def test_replaces_single_select_junction(conn, redis_client):
    fid, old_name, _, _, _ = await _create_with_junctions(conn, redis_client)
    new_name = await create_name(conn, f"n-{_u()}", redis_client)

    await update_field(conn, fid, name_id=new_name.id)

    items = await get_fields(conn, [fid], names=True)
    assert items[0].name_ids == [new_name.id]


async def test_keeps_unchanged_single_junction(conn, redis_client):
    fid, name_id, _, _, _ = await _create_with_junctions(conn, redis_client)

    await update_field(conn, fid, name_id=name_id)

    items = await get_fields(conn, [fid], names=True)
    assert items[0].name_ids == [name_id]


async def test_skips_junction_when_unset(conn, redis_client):
    fid, name_id, desc_id, _, _ = await _create_with_junctions(conn, redis_client)
    new_desc = await create_description(conn, f"d-{_u()}", redis_client)

    # Only update description_id, leave name_id unset
    await update_field(conn, fid, description_id=new_desc.id)

    items = await get_fields(conn, [fid], names=True, descriptions=True)
    assert items[0].name_ids == [name_id]  # unchanged
    assert items[0].description_ids == [new_desc.id]  # updated


async def test_deactivates_removed_multi_ids(conn, redis_client):
    fid, _, _, d1, d2 = await _create_with_junctions(conn, redis_client)

    await update_field(conn, fid, department_ids=[d1])

    items = await get_fields(conn, [fid], departments=True)
    assert items[0].department_ids == [d1]


async def test_adds_new_multi_ids(conn, redis_client):
    fid, _, _, d1, d2 = await _create_with_junctions(conn, redis_client)
    d3 = await create_department(conn, redis=redis_client)

    await update_field(conn, fid, department_ids=[d1, d2, d3.id])

    items = await get_fields(conn, [fid], departments=True)
    assert set(items[0].department_ids) == {d1, d2, d3.id}


async def test_clears_all_multi_ids(conn, redis_client):
    fid, _, _, _, _ = await _create_with_junctions(conn, redis_client)

    await update_field(conn, fid, department_ids=[])

    items = await get_fields(conn, [fid], departments=True)
    assert items[0].department_ids == []


async def test_updates_flags(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    result = await create_field(conn, flag_ids=[f1.id])

    await update_field(conn, result.id, flag_ids=[f2.id])

    # f1 replaced by f2
    items = await get_fields(conn, [result.id], flags=True)
    assert items[0].flag_ids == [f2.id]


async def test_multi_none_means_no_change(conn, redis_client):
    fid, _, _, d1, d2 = await _create_with_junctions(conn, redis_client)

    await update_field(conn, fid, department_ids=None)

    items = await get_fields(conn, [fid], departments=True)
    assert set(items[0].department_ids) == {d1, d2}
