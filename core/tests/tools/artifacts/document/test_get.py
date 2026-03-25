"""Tests for get_documents."""

import pytest
from tests.helpers import nonexistent_id, unique_tag

from app.tools.artifacts.document.create import create_document
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.update import update_document
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


async def test_returns_base_columns(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_document(conn, name_id=name.id)

    items = await get_documents(conn, [created.id])

    assert len(items) == 1
    p = items[0]
    assert p.id == created.id
    # No junctions requested — all should be None
    assert p.name_ids is None
    assert p.description_ids is None
    assert p.department_ids is None


async def test_returns_empty_for_unknown_id(conn):

    items = await get_documents(conn, [nonexistent_id()])
    assert items == []


async def test_returns_empty_for_empty_ids(conn):
    items = await get_documents(conn, [])
    assert items == []


async def test_fetches_name_ids_when_requested(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_document(conn, name_id=name.id)

    items = await get_documents(conn, [created.id], names=True)

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    # Other junctions still None
    assert p.description_ids is None


async def test_fetches_multiple_junctions(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_document(conn, name_id=name.id)

    items = await get_documents(
        conn,
        [created.id],
        names=True,
        descriptions=True,
        flags=True,
    )

    assert len(items) == 1
    p = items[0]
    assert p.name_ids is not None
    assert p.description_ids is not None
    assert p.flag_ids is not None
    # Unrequested junctions stay None
    assert p.department_ids is None
    assert p.files_ids is None


async def test_no_junctions_when_all_false(conn, redis_client):
    name = await create_name(conn, f"test-{unique_tag()}", redis_client)
    created = await create_document(conn, name_id=name.id)

    items = await get_documents(conn, [created.id])

    p = items[0]
    for field in [
        "name_ids",
        "description_ids",
        "department_ids",
        "flag_ids",
        "files_ids",
        "images_ids",
        "parameter_field_ids",
        "parameter_ids",
        "texts_ids",
        "document_ids",
    ]:
        assert getattr(p, field) is None


async def test_hides_inactive_by_default(conn):
    created = await create_document(conn)
    await update_document(conn, created.id, active=False)

    items = await get_documents(conn, [created.id])

    assert items == []


async def test_returns_inactive_when_active_filter_is_none(conn):
    created = await create_document(conn)
    await update_document(conn, created.id, active=False)

    items = await get_documents(conn, [created.id], active=None)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].active is False


async def test_can_filter_for_only_inactive(conn):
    active_item = await create_document(conn)
    inactive_item = await create_document(conn)
    await update_document(conn, inactive_item.id, active=False)

    items = await get_documents(
        conn,
        [active_item.id, inactive_item.id],
        active=False,
    )

    assert [item.id for item in items] == [inactive_item.id]
    assert items[0].active is False
