"""Tests for get_personas."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.persona.create import create_persona
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.update import update_persona
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


async def test_returns_base_columns(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_persona(conn, name_id=name.id)

    items = await get_personas(conn, [created.id])

    assert len(items) == 1
    p = items[0]
    assert p.id == created.id
    assert p.active is True
    # No junctions requested — all should be None
    assert p.name_ids is None
    assert p.description_ids is None
    assert p.color_ids is None


async def test_returns_empty_for_unknown_id(conn):

    items = await get_personas(conn, [nonexistent_id()])
    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_personas(conn, [])
    assert items == []


async def test_fetches_name_ids_when_requested(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_persona(conn, name_id=name.id)

    items = await get_personas(conn, [created.id], names=True)

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    assert len(p.name_ids) > 0
    # Other junctions still None
    assert p.description_ids is None


async def test_fetches_multiple_junctions(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_persona(conn, name_id=name.id)

    items = await get_personas(
        conn,
        [created.id],
        names=True,
        descriptions=True,
        colors=True,
    )

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    # descriptions and colors may be empty lists if no seed data, but not None
    assert p.description_ids is not None
    assert p.color_ids is not None
    # Unrequested junctions stay None
    assert p.flag_ids is None
    assert p.voice_ids is None


async def test_no_junctions_when_all_false(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_persona(conn, name_id=name.id)

    items = await get_personas(conn, [created.id])

    p = items[0]
    for field in [
        "name_ids",
        "description_ids",
        "color_ids",
        "department_ids",
        "example_ids",
        "flag_ids",
        "icon_ids",
        "instruction_ids",
        "parameter_field_ids",
        "persona_ids",
        "voice_ids",
    ]:
        assert getattr(p, field) is None


async def test_hides_inactive_by_default(conn):
    created = await create_persona(conn)
    await update_persona(conn, created.id, active=False)

    items = await get_personas(conn, [created.id])

    assert items == []


async def test_returns_inactive_when_active_filter_is_none(conn):
    created = await create_persona(conn)
    await update_persona(conn, created.id, active=False)

    items = await get_personas(conn, [created.id], active=None)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].active is False


async def test_can_filter_for_only_inactive(conn):
    active_persona = await create_persona(conn)
    inactive_persona = await create_persona(conn)
    await update_persona(conn, inactive_persona.id, active=False)

    items = await get_personas(
        conn,
        [active_persona.id, inactive_persona.id],
        active=False,
    )

    assert [item.id for item in items] == [inactive_persona.id]
    assert items[0].active is False
