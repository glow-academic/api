"""Tests for create_persona — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.persona.create import create_persona
from app.tools.artifacts.persona.get import get_personas
from app.tools.resources.colors.create import create_color
from app.tools.resources.departments.create import create_department
from app.tools.resources.examples.create import create_example
from app.tools.resources.flags.create import create_flag
from app.tools.resources.icons.create import create_icon
from app.tools.resources.names.create import create_name
from app.tools.resources.voices.create import create_voice

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
    result = await create_persona(conn)
    assert result.id is not None

    items = await get_personas(conn, [result.id])
    assert len(items) == 1
    assert items[0].active is True
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_persona(conn, mcp=True)

    items = await get_personas(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    color = await create_color(conn, f"c-{_u()}", "desc", f"#{_u()[:6]}", redis_client)
    icon = await create_icon(conn, f"i-{_u()}", "desc", f"val-{_u()}", redis_client)

    result = await create_persona(
        conn, name_id=name.id, color_id=color.id, icon_id=icon.id
    )

    items = await get_personas(conn, [result.id], names=True, colors=True, icons=True)
    p = items[0]
    assert p.name_ids == [name.id]
    assert p.color_ids == [color.id]
    assert p.icon_ids == [icon.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    v1 = await create_voice(conn, f"v-{_u()}", redis_client)

    result = await create_persona(
        conn, department_ids=[d1.id, d2.id], voice_ids=[v1.id]
    )

    items = await get_personas(conn, [result.id], departments=True, voices=True)
    p = items[0]
    assert set(p.department_ids) == {d1.id, d2.id}
    assert p.voice_ids == [v1.id]


async def test_links_examples(conn, redis_client):
    e1 = await create_example(conn, "ex1", redis_client)
    e2 = await create_example(conn, "ex2", redis_client)

    result = await create_persona(conn, example_ids=[e1.id, e2.id])

    items = await get_personas(conn, [result.id], examples=True)
    assert set(items[0].example_ids) == {e1.id, e2.id}


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_persona(conn, flag_ids=[f1.id, f2.id])

    items = await get_personas(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_persona(conn)

    items = await get_personas(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        colors=True,
        departments=True,
        examples=True,
        flags=True,
        icons=True,
        instructions=True,
        parameter_fields=True,
        personas=True,
        voices=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.department_ids == []
    assert p.flag_ids == []
