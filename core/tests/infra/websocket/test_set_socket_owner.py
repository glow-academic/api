"""Tests for set_socket_owner — atomic first-socket detection (D1).

The connect path (``ws/connect.py``) records a presence/activity row only when
``set_socket_owner`` returns True (this is the *first* socket for the profile).
The old implementation read SCARD in a SEPARATE round-trip after a pipelined
SADD and compared ``scard == added``: two tabs connecting into an empty set
each SADD a distinct sid (both added=1), then both SCARD reads saw size=2, so
``2 == 1`` was False for BOTH → neither was first → presence/activity was never
written. The fix moves the add + size check into ONE atomic server-side Lua
script.

These tests run against the real Redis testcontainer (``redis_client``) and
drive the genuine race: many concurrent ``set_socket_owner`` calls into an
empty set must yield EXACTLY ONE first-socket winner.
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.infra.websocket.set_socket_owner import set_socket_owner

pytestmark = pytest.mark.asyncio


async def test_single_connect_is_first(redis_client):
    """A lone socket into an empty set is the first socket."""
    profile_id = str(uuid4())
    assert await set_socket_owner(profile_id, str(uuid4()), redis_client=redis_client) is True


async def test_second_connect_is_not_first(redis_client):
    """A second distinct socket for the same profile is NOT first."""
    profile_id = str(uuid4())
    first = await set_socket_owner(profile_id, str(uuid4()), redis_client=redis_client)
    second = await set_socket_owner(profile_id, str(uuid4()), redis_client=redis_client)
    assert first is True
    assert second is False


async def test_readd_same_socket_is_not_first(redis_client):
    """Re-adding an already-present sid is never 'first' (no presence
    transition) — preserves the original contract."""
    profile_id, sid = str(uuid4()), str(uuid4())
    assert await set_socket_owner(profile_id, sid, redis_client=redis_client) is True
    # Same sid again: SADD adds nothing.
    assert await set_socket_owner(profile_id, sid, redis_client=redis_client) is False


async def test_concurrent_first_connects_exactly_one_winner(redis_client):
    """The D1 race: N tabs connect concurrently into an empty set. EXACTLY ONE
    must see is_first=True (so presence/activity is written once). Pre-fix this
    returned 0 winners (the bug); the fix returns exactly 1."""
    profile_id = str(uuid4())
    sids = [str(uuid4()) for _ in range(10)]

    results = await asyncio.gather(
        *(set_socket_owner(profile_id, sid, redis_client=redis_client) for sid in sids)
    )

    assert sum(1 for r in results if r is True) == 1, results
    # All 10 sockets landed in the set regardless of who won.
    assert await redis_client.scard(f"socket_owners:{profile_id}") == 10


async def test_reverse_mapping_written(redis_client):
    """The socket→profile reverse mapping is written for find_profile_by_socket."""
    profile_id, sid = str(uuid4()), str(uuid4())
    await set_socket_owner(profile_id, sid, redis_client=redis_client)
    val = await redis_client.get(f"socket_to_profile:{sid}")
    if isinstance(val, bytes):
        val = val.decode()
    assert val == profile_id
