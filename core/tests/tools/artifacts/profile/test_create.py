"""Tests for create_profile — black-box using resource + artifact tools only."""

import pytest
from tests.helpers import unique_tag

from app.tools.artifacts.profile.create import create_profile
from app.tools.artifacts.profile.get import get_profiles
from app.tools.resources.departments.create import create_department
from app.tools.resources.emails.create import create_email
from app.tools.resources.flags.create import create_flag
from app.tools.resources.names.create import create_name
from app.tools.resources.request_limits.create import create_request_limit

pytestmark = pytest.mark.asyncio


def _u() -> str:
    return unique_tag()


async def test_creates_bare_artifact(conn, redis_client):
    result = await create_profile(conn)
    assert result.id is not None

    items = await get_profiles(conn, [result.id])
    assert len(items) == 1
    assert items[0].generated is False
    assert items[0].mcp is False


async def test_passes_mcp_flag(conn, redis_client):
    result = await create_profile(conn, mcp=True)

    items = await get_profiles(conn, [result.id])
    assert items[0].mcp is True


async def test_links_single_select_junctions(conn, redis_client):
    name = await create_name(conn, f"n-{_u()}", redis_client)

    result = await create_profile(conn, name_id=name.id)

    items = await get_profiles(conn, [result.id], names=True)
    p = items[0]
    assert p.name_ids == [name.id]


async def test_links_multi_select_junctions(conn, redis_client):
    d1 = await create_department(conn, redis=redis_client)
    d2 = await create_department(conn, redis=redis_client)

    result = await create_profile(conn, department_ids=[d1.id, d2.id])

    items = await get_profiles(conn, [result.id], departments=True)
    assert set(items[0].department_ids) == {d1.id, d2.id}


async def test_links_email_junctions_via_resource_get(conn, redis_client):
    e1 = await create_email(conn, f"first-{_u()}@example.com", redis_client)
    e2 = await create_email(conn, f"second-{_u()}@example.com", redis_client)

    result = await create_profile(conn, email_ids=[e1.id, e2.id], redis=redis_client)

    items = await get_profiles(conn, [result.id], emails=True)
    assert set(items[0].email_ids) == {e1.id, e2.id}


async def test_links_request_limit_junction_via_resource_get(conn, redis_client):
    limit = await create_request_limit(conn, 42, redis_client)

    result = await create_profile(
        conn,
        request_limit_id=limit.id,
        redis=redis_client,
    )

    items = await get_profiles(conn, [result.id], request_limits=True)
    assert items[0].request_limit_ids == [limit.id]


async def test_links_flags_with_value(conn, redis_client):
    f1 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)
    f2 = await create_flag(conn, f"f-{_u()}", "desc", "icon", redis_client)

    result = await create_profile(conn, flag_ids=[f1.id, f2.id])

    items = await get_profiles(conn, [result.id], flags=True)
    assert set(items[0].flag_ids) == {f1.id, f2.id}


async def test_no_junctions_when_none_provided(conn, redis_client):
    result = await create_profile(conn)

    items = await get_profiles(
        conn,
        [result.id],
        names=True,
        departments=True,
        flags=True,
        emails=True,
        profiles=True,
        request_limits=True,
        roles=True,
    )
    p = items[0]
    assert p.name_ids == []
    assert p.department_ids == []
    assert p.flag_ids == []
    assert p.email_ids == []
    assert p.profile_ids == []
    assert p.request_limit_ids == []
    assert p.role_ids == []
