"""Tests for create_auth — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.auth.create import create_auth
from app.tools.artifacts.auth.get import get_auths
from app.tools.resources.departments.create import create_department
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.flags.create import create_flag
from app.tools.resources.items.create import create_item
from app.tools.resources.names.create import create_name
from app.tools.resources.slugs.create import create_slug

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
    result = await create_auth(conn)
    assert result.id is not None

    items = await get_auths(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_auth(conn, mcp=True)

    items = await get_auths(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)
    desc = await create_description(conn, f"d-{_u()}", redis_client)
    slug = await create_slug(conn, f"s-{_u()}", redis_client)

    result = await create_auth(
        conn, name_id=name.id, description_id=desc.id, slug_id=slug.id
    )

    items = await get_auths(
        conn, [result.id], names=True, descriptions=True, slugs=True
    )
    p = items[0]
    assert p.name_ids == [name.id]
    assert p.description_ids == [desc.id]
    assert p.slug_ids == [slug.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)
    i1 = await create_item(conn, f"item-{_u()}", "desc", redis_client)

    result = await create_auth(conn, department_ids=[d1.id, d2.id], item_ids=[i1.id])

    items = await get_auths(conn, [result.id], departments=True, items=True)
    p = items[0]
    assert set(p.department_ids) == {d1.id, d2.id}
    assert p.item_ids == [i1.id]


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_auth(conn, flag_ids=[f1.id, f2.id])

    items = await get_auths(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_auth(conn)

    items = await get_auths(
        conn,
        [result.id],
        names=True,
        descriptions=True,
        departments=True,
        flags=True,
        items=True,
        protocols=True,
        slugs=True,
        auths=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.department_ids == []
    assert p.flag_ids == []
    assert p.auth_ids == []
