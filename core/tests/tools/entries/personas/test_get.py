"""Tests for get_personas."""

import pytest
from app.tools.entries.personas.create import create_personas
from app.tools.entries.personas.get import get_personas
from app.tools.entries.sessions.create import create_session
from tests.helpers import nonexistent_id

pytestmark = pytest.mark.asyncio


async def _session(conn, redis_client, profile_id):
    return await create_session(conn, redis_client, profile_id=profile_id)


def _created(result):
    return result[0] if isinstance(result, tuple) else result


async def test_gets_created_personas(conn, redis_client):
    created = _created(await create_personas(conn, redis_client))
    lookup_id = getattr(created, 'id', None) or getattr(created, 'id', None)
    items = await get_personas(conn, ids=[lookup_id], redis=redis_client)

    assert len(items) >= 1
    assert items[0].id == lookup_id


async def test_returns_empty_for_missing_id(conn, redis_client):
    items = await get_personas(conn, ids=[nonexistent_id()], redis=redis_client)

    assert items == []


async def test_returns_empty_for_empty_ids(conn, redis_client):
    items = await get_personas(conn, ids=[], redis=redis_client)

    assert items == []


async def test_batch_get_returns_all_in_id_order(conn, redis_client):
    """Multiple ids resolve correctly and preserve the requested order."""
    created = [
        _created(await create_personas(conn, redis_client)) for _ in range(4)
    ]
    ids = [c.id for c in created]
    # request in a shuffled order to prove ordering is by requested ids
    requested = [ids[2], ids[0], ids[3], ids[1]]

    items = await get_personas(conn, ids=requested, redis=redis_client)

    assert [i.id for i in items] == requested


class _CountingRedis:
    """Wraps a Redis client, counting get/mget calls, delegating everything else."""

    def __init__(self, inner):
        self._inner = inner
        self.get_calls = 0
        self.mget_calls = 0

    async def get(self, *a, **k):
        self.get_calls += 1
        return await self._inner.get(*a, **k)

    async def mget(self, *a, **k):
        self.mget_calls += 1
        return await self._inner.mget(*a, **k)

    def __getattr__(self, name):
        return getattr(self._inner, name)


async def test_cache_phase_uses_single_mget_not_per_id_get(conn, redis_client):
    """The cache-read phase must batch into one MGET, not N per-id GETs."""
    created = [
        _created(await create_personas(conn, redis_client)) for _ in range(5)
    ]
    ids = [c.id for c in created]

    counting = _CountingRedis(redis_client)
    items = await get_personas(conn, ids=ids, redis=counting)

    # Correctness preserved: all rows returned, in order.
    assert [i.id for i in items] == ids
    # Batch path: exactly one MGET for the cache phase, zero per-id GETs.
    assert counting.mget_calls == 1
    assert counting.get_calls == 0


async def test_batch_and_perid_paths_agree(conn, redis_client):
    """Batch MGET result equals the row-by-row read_back_row result."""
    from app.utils.cache.hedged_row import read_back_row, read_back_rows

    created = [
        _created(await create_personas(conn, redis_client)) for _ in range(3)
    ]
    ids = [c.id for c in created]

    per_id = {}
    for i in ids:
        row = await read_back_row(redis_client, "personas", i)
        if row is not None:
            per_id[str(i)] = row
    batch = await read_back_rows(redis_client, "personas", list(ids))

    assert batch == per_id
