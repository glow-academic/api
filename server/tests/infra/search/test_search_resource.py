"""Tests for generic resource search helper."""

from uuid import uuid4

import pytest

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.names.create import create_name

pytestmark = pytest.mark.asyncio


async def test_search_resource_ids_returns_empty_for_non_positive_limit(conn):
    result = await search_resource_ids(
        conn,
        table="names_resource",
        resource="names",
        search_column="name",
        limit_count=0,
    )

    assert result == []


async def test_search_resource_ids_filters_by_search_and_excludes_ids(
    conn, redis_client
):
    token = uuid4().hex[:8]
    alpha = await create_name(conn, f"doc-{token}-alpha", redis_client)
    beta = await create_name(conn, f"doc-{token}-beta", redis_client)
    gamma = await create_name(conn, f"notes-{token}-gamma", redis_client)

    result = await search_resource_ids(
        conn,
        table="names_resource",
        resource="names",
        search_column="name",
        search=f"doc-{token}",
        exclude_ids=[beta.id],
        order_column="name",
    )

    assert result == [alpha.id]
    assert gamma.id not in result


async def test_search_resource_ids_supports_additional_search_columns_and_offset(
    conn, redis_client
):
    token = uuid4().hex[:8]
    first = await create_name(conn, f"case-{token}-a", redis_client)
    second = await create_name(conn, f"case-{token}-b", redis_client)
    await create_name(conn, f"archive-{token}", redis_client)

    result = await search_resource_ids(
        conn,
        table="names_resource",
        resource="names",
        search_column="name",
        additional_search_columns=["name"],
        search=f"case-{token}",
        order_column="name",
        limit_count=1,
        offset_count=1,
    )

    assert result == [second.id]
    assert first.id not in result
