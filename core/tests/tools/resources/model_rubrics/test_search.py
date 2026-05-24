"""Tests for search_model_rubrics."""

import pytest
from tests.helpers import unique_tag

from app.tools.resources.model_rubrics.create import create_model_rubric
from app.tools.resources.model_rubrics.search import search_model_rubrics
from app.tools.resources.models.create import create_model
from app.tools.resources.rubrics.create import create_rubric

pytestmark = pytest.mark.asyncio


async def _create_model_rubric_with_deps(conn, redis_client):
    """Helper: create a model + rubric + model_rubric."""
    model = await create_model(conn, value=f"model-{unique_tag()}", redis=redis_client)
    rubric = await create_rubric(conn, redis_client, name=f"rubric-{unique_tag()}")
    mr = await create_model_rubric(conn, model.id, rubric.id, redis_client)
    return mr


async def test_finds_created_model_rubric(conn, redis_client):
    mr = await _create_model_rubric_with_deps(conn, redis_client)

    items = await search_model_rubrics(conn, redis_client, limit_count=1000)

    ids = [i.id for i in items]
    assert mr.id in ids


async def test_respects_limit(conn, redis_client):
    for _ in range(3):
        await _create_model_rubric_with_deps(conn, redis_client)

    items = await search_model_rubrics(conn, redis_client, limit_count=2)

    assert len(items) <= 2


async def test_respects_offset(conn, redis_client):
    for _ in range(3):
        await _create_model_rubric_with_deps(conn, redis_client)

    all_items = await search_model_rubrics(conn, redis_client, limit_count=1000)
    offset_items = await search_model_rubrics(
        conn, redis_client, limit_count=1000, offset_count=1
    )

    assert len(offset_items) == len(all_items) - 1


async def test_excludes_ids(conn, redis_client):
    a = await _create_model_rubric_with_deps(conn, redis_client)
    b = await _create_model_rubric_with_deps(conn, redis_client)

    items = await search_model_rubrics(
        conn, redis_client, limit_count=1000, exclude_ids=[a.id]
    )

    ids = [i.id for i in items]
    assert a.id not in ids
    assert b.id in ids


async def test_returns_empty_for_zero_limit(conn, redis_client):
    items = await search_model_rubrics(conn, redis_client, limit_count=0)

    assert items == []


async def test_cache_hit(conn, redis_client):
    await _create_model_rubric_with_deps(conn, redis_client)

    items1 = await search_model_rubrics(conn, redis_client, limit_count=1000)
    items2 = await search_model_rubrics(conn, redis_client, limit_count=1000)

    assert len(items1) >= 1
    assert len(items1) == len(items2)


async def test_bypass_cache(conn, redis_client):
    await _create_model_rubric_with_deps(conn, redis_client)

    items = await search_model_rubrics(
        conn, redis_client, limit_count=1000, bypass_cache=True
    )

    assert len(items) >= 1
