"""Tests for update_department — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.department.create import (
    create_department as create_dept_artifact,
)
from app.tools.artifacts.department.get import get_departments
from app.tools.artifacts.department.update import update_department
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name
from app.tools.resources.settings.create import create_setting

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u() -> str:
    return unique_tag()


async def _create_with_junctions(conn, redis_client):
    """Create a department with single + multi junctions for update tests."""
    n = await create_name(conn, f"n-{_u()}", redis_client)
    s1 = await create_setting(conn, redis=redis_client)
    s2 = await create_setting(conn, redis=redis_client)

    result = await create_dept_artifact(conn, name_id=n.id, settings_ids=[s1.id, s2.id])
    return result.id, n.id, s1.id, s2.id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_updates_mcp(conn, redis_client):
    result = await create_dept_artifact(conn)
    await update_department(conn, result.id, mcp=True)

    items = await get_departments(conn, [result.id])
    assert items[0].mcp is True


async def test_replaces_single_select_junction(conn, redis_client):
    did, old_name, _, _ = await _create_with_junctions(conn, redis_client)
    new_name = await create_name(conn, f"n-{_u()}", redis_client)

    await update_department(conn, did, name_id=new_name.id)

    items = await get_departments(conn, [did], names=True)
    assert items[0].name_ids == [new_name.id]


async def test_keeps_unchanged_single_junction(conn, redis_client):
    did, name_id, _, _ = await _create_with_junctions(conn, redis_client)

    await update_department(conn, did, name_id=name_id)

    items = await get_departments(conn, [did], names=True)
    assert items[0].name_ids == [name_id]


async def test_skips_junction_when_unset(conn, redis_client):
    did, name_id, _, _ = await _create_with_junctions(conn, redis_client)

    # Update with no junction args — name should be untouched
    await update_department(conn, did)

    items = await get_departments(conn, [did], names=True)
    assert items[0].name_ids == [name_id]


async def test_deactivates_removed_multi_ids(conn, redis_client):
    did, _, s1, s2 = await _create_with_junctions(conn, redis_client)

    await update_department(conn, did, settings_ids=[s1])

    items = await get_departments(conn, [did], settings=True)
    assert items[0].settings_ids == [s1]


async def test_adds_new_multi_ids(conn, redis_client):
    did, _, s1, s2 = await _create_with_junctions(conn, redis_client)
    s3 = await create_setting(conn, redis=redis_client)

    await update_department(conn, did, settings_ids=[s1, s2, s3.id])

    items = await get_departments(conn, [did], settings=True)
    assert set(items[0].settings_ids) == {s1, s2, s3.id}


async def test_clears_all_multi_ids(conn, redis_client):
    did, _, s1, s2 = await _create_with_junctions(conn, redis_client)

    await update_department(conn, did, settings_ids=[])

    items = await get_departments(conn, [did], settings=True)
    assert items[0].settings_ids == []


async def test_updates_flags(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    result = await create_dept_artifact(conn, flag_ids=[f1.id])

    await update_department(conn, result.id, flag_ids=[f2.id])

    # f1 replaced by f2
    items = await get_departments(conn, [result.id], flags=True)
    assert items[0].flag_ids == [f2.id]


async def test_multi_none_means_no_change(conn, redis_client):
    did, _, s1, s2 = await _create_with_junctions(conn, redis_client)

    await update_department(conn, did, settings_ids=None)

    items = await get_departments(conn, [did], settings=True)
    assert set(items[0].settings_ids) == {s1, s2}
