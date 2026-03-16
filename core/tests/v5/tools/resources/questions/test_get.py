"""Tests for get_questions."""

import pytest
from tests.helpers import nonexistent_id

from app.tools.resources.questions.create import create_question
from app.tools.resources.questions.get import get_questions

pytestmark = pytest.mark.asyncio


async def test_gets_created_question(conn, redis_client):
    created = await create_question(conn, "What is your name?", 30, redis_client)

    items = await get_questions(conn, [created.id], redis_client)

    assert len(items) == 1
    assert items[0].id == created.id
    assert items[0].question_text == "What is your name?"
    assert items[0].time == 30
    assert items[0].active is True


async def test_returns_empty_for_missing_question(conn, redis_client):
    items = await get_questions(conn, [nonexistent_id()], redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_questions(conn, [], redis_client)

    assert items == []


async def test_cache_hit_skips_db(conn, redis_client):
    created = await create_question(
        conn, "What is your favorite color?", 60, redis_client
    )

    items = await get_questions(conn, [created.id], redis_client)
    assert len(items) == 1

    items2 = await get_questions(conn, [created.id], redis_client)
    assert len(items2) == 1
    assert items2[0].question_text == "What is your favorite color?"


async def test_bypass_cache_skips_read_and_write(conn, redis_client):
    created = await create_question(conn, "What is your age?", 45, redis_client)

    items = await get_questions(conn, [created.id], redis_client, bypass_cache=True)
    assert len(items) == 1

    from app.utils.cache.cache_key import cache_key
    from app.utils.cache.get_cached import get_cached

    key = cache_key("/v5/resources/questions/get", {"ids": [str(created.id)]})
    cached = await get_cached(key, redis=redis_client)
    assert cached is None
