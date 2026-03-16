"""Tests for create_department — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.department.create import (
    create_department as create_dept_artifact,
)
from app.tools.artifacts.department.get import get_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name
from app.tools.resources.settings.create import create_setting

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _u() -> str:
    return unique_tag()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_creates_bare_artifact(conn, redis_client):
    result = await create_dept_artifact(conn)
    assert result.id is not None

    items = await get_departments(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_dept_artifact(conn, mcp=True)

    items = await get_departments(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)

    result = await create_dept_artifact(conn, name_id=name.id, description_id=desc.id)

    items = await get_departments(conn, [result.id], names=True, descriptions=True)
    p = items[0]
    assert p.name_ids == [name.id]
    assert p.description_ids == [desc.id]


async def test_links_multi_select_junctions(conn, redis_client):
    s1 = await create_setting(conn, redis=redis_client)
    s2 = await create_setting(conn, redis=redis_client)

    result = await create_dept_artifact(conn, settings_ids=[s1.id, s2.id])

    items = await get_departments(conn, [result.id], settings=True)
    assert set(items[0].settings_ids) == {s1.id, s2.id}


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_dept_artifact(conn, flag_ids=[f1.id, f2.id])

    items = await get_departments(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_dept_artifact(conn)

    items = await get_departments(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        flags=True,
        settings=True,
        departments=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.flag_ids == []
    assert p.settings_ids == []
    assert p.department_ids == []
