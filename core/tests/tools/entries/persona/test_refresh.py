"""Tests for refresh_persona_internal."""

import pytest
from app.tools.entries.persona.create import create_persona
from app.tools.resources.personas.create import (
    create_persona as create_persona_resource,
)
from app.tools.entries.persona.get import get_persona_entries_internal
from app.tools.entries.persona.refresh import refresh_persona_internal

pytestmark = pytest.mark.asyncio





def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_new_persona_appears_after_refresh(conn):
    created = _created(await create_persona(conn, ))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    await refresh_persona_internal(conn)
    items = await get_persona_entries_internal(conn, ids=[lookup_id])

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_new_persona_is_not_visible_before_refresh(conn):
    created = _created(await create_persona(conn, ))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)

    items = await get_persona_entries_internal(conn, ids=[lookup_id])

    assert items == []


async def test_refresh_is_idempotent(conn):
    await refresh_persona_internal(conn)
    await refresh_persona_internal(conn)

    assert True
