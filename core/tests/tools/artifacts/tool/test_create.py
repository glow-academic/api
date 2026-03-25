"""Tests for create_tool — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.tool.create import (
    create_tool as create_tool_artifact,
)
from app.tools.artifacts.tool.get import get_tools
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name
from app.tools.resources.tools.create import (
    create_tool as create_tool_resource,
)

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
    result = await create_tool_artifact(conn)
    assert result.id is not None

    items = await get_tools(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_tool_artifact(conn, mcp=True)

    items = await get_tools(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)

    result = await create_tool_artifact(conn, name_id=name.id, description_id=desc.id)

    items = await get_tools(conn, [result.id], names=True, descriptions=True)
    t = items[0]
    assert t.name_ids == [name.id]
    assert t.description_ids == [desc.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    # tool_tools_junction references tools_resource, not tool_artifact
    tool_res = await create_tool_resource(conn, redis=redis_client)

    result = await create_tool_artifact(
        conn,
        department_ids=[d1.id, d2.id],
        tool_ids=[tool_res.id],
    )

    items = await get_tools(conn, [result.id], departments=True, tools=True)
    t = items[0]
    assert set(t.department_ids) == {d1.id, d2.id}
    assert t.tool_ids == [tool_res.id]


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_tool_artifact(conn, flag_ids=[f1.id, f2.id])

    items = await get_tools(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_tool_artifact(conn)

    items = await get_tools(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        departments=True,
        flags=True,
        args=True,
        args_outputs=True,
        arg_positions=True,
        artifacts=True,
        operations=True,
        tools=True,
    )
    t = items[0]
    assert t.name_ids == []
    assert t.description_ids == []
    assert t.department_ids == []
    assert t.flag_ids == []
    assert t.args_ids == []
    assert t.args_outputs_ids == []
    assert t.arg_positions_ids == []
    assert t.artifact_ids == []
    assert t.operation_ids == []
    assert t.tool_ids == []
