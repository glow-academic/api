"""Tests for get_providers."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.provider.create import create_provider
from app.tools.artifacts.provider.get import get_providers
from app.tools.artifacts.provider.update import update_provider
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


async def test_returns_base_columns(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_provider(conn, name_id=name.id)

    items = await get_providers(conn, [created.id])

    assert len(items) == 1
    p = items[0]
    assert p.id == created.id
    # No junctions requested — all should be None
    assert p.name_ids is None
    assert p.description_ids is None
    assert p.department_ids is None
    assert p.flag_ids is None
    assert p.endpoint_ids is None
    assert p.key_ids is None
    assert p.value_ids is None
    assert p.provider_ids is None


async def test_returns_empty_for_unknown_id(conn):

    items = await get_providers(conn, [nonexistent_id()])
    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_providers(conn, [])
    assert items == []


async def test_fetches_name_ids_when_requested(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_provider(conn, name_id=name.id)

    items = await get_providers(conn, [created.id], names=True)

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    # Other junctions still None
    assert p.description_ids is None


async def test_fetches_multiple_junctions(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_provider(conn, name_id=name.id)

    items = await get_providers(
        conn,
        [created.id],
        names=True,
        descriptions=True,
        departments=True,
    )

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    assert p.description_ids is not None
    assert p.department_ids is not None
    # Unrequested junctions stay None
    assert p.flag_ids is None
    assert p.endpoint_ids is None


async def test_no_junctions_when_all_false(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_provider(conn, name_id=name.id)

    items = await get_providers(conn, [created.id])

    p = items[0]
    for field in [
        "name_ids",
        "description_ids",
        "department_ids",
        "flag_ids",
        "endpoint_ids",
        "key_ids",
        "value_ids",
        "provider_ids",
    ]:
        assert getattr(p, field) is None


async def test_hides_inactive_by_default(conn):
    created = await create_provider(conn)
    await update_provider(conn, created.id, active=False)

    items = await get_providers(conn, [created.id])

    assert items == []


async def test_returns_inactive_when_active_filter_is_none(conn):
    created = await create_provider(conn)
    await update_provider(conn, created.id, active=False)

    items = await get_providers(conn, [created.id], active=None)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].active is False


async def test_can_filter_for_only_inactive(conn):
    active_item = await create_provider(conn)
    inactive_item = await create_provider(conn)
    await update_provider(conn, inactive_item.id, active=False)

    items = await get_providers(
        conn,
        [active_item.id, inactive_item.id],
        active=False,
    )

    assert [item.id for item in items] == [inactive_item.id]
    assert items[0].active is False
