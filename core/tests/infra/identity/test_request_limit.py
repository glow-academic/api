"""RL1/RL2: per-profile request-rate enforcement (enforce_request_limit)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.infra.identity.request_limit import (
    enforce_request_limit,
    interval_to_seconds,
)


class _FakeRedis:
    """Minimal async Redis fake implementing the RL-B2 atomic ``eval`` path.

    ``enforce_request_limit`` runs a single Lua ``INCR`` + arm-TTL-iff-unset via
    ``redis.eval``. This fake reproduces those semantics in-memory: it INCRs the
    counter and arms the TTL exactly once (when none is set), so a TTL can never
    be lost (no forever-429) and a live window is never extended (no ~2x slide).
    ``arm_count`` records how many times the TTL was actually armed.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self._counts: dict[str, int] = {}
        self.expires: dict[str, int] = {}
        self._fail = fail
        self.arm_count = 0

    async def eval(self, script: str, numkeys: int, *keys_and_args):
        if self._fail:
            raise RuntimeError("redis down")
        key = keys_and_args[0]
        ttl = int(keys_and_args[numkeys])  # ARGV[1]
        self._counts[key] = self._counts.get(key, 0) + 1
        if key not in self.expires:  # TTL < 0 → arm it (atomic with the INCR)
            self.expires[key] = ttl
            self.arm_count += 1
        return self._counts[key]


def test_interval_to_seconds_parses_common_forms():
    assert interval_to_seconds("1 day") == 86400
    assert interval_to_seconds("30 minutes") == 1800
    assert interval_to_seconds("1 hour") == 3600
    assert interval_to_seconds("hour") == 3600  # qty defaults to 1
    assert interval_to_seconds("2 weeks") == 2 * 604800


@pytest.mark.parametrize("bad", [None, "", "   ", "banana", "lots of time"])
def test_interval_to_seconds_falls_back_to_one_day(bad):
    assert interval_to_seconds(bad) == 86400


@pytest.mark.asyncio
@pytest.mark.parametrize("no_limit", [None, 0, -5])
async def test_no_quota_is_a_noop(no_limit):
    redis = _FakeRedis()
    await enforce_request_limit(
        redis, profile_id=uuid4(), request_limit=no_limit,
        request_limit_interval="1 day", operation="generate",
    )
    assert redis._counts == {}  # never touched the counter


@pytest.mark.asyncio
async def test_allows_up_to_limit_then_rejects():
    redis = _FakeRedis()
    pid = uuid4()

    # The first ``limit`` calls are allowed.
    for _ in range(3):
        await enforce_request_limit(
            redis, profile_id=pid, request_limit=3,
            request_limit_interval="1 day", operation="generate",
        )

    # The TTL was started exactly once, on the first call.
    assert redis.expires[f"reqlimit:{pid}:generate"] == 86400

    # The 4th call (count > limit) is rejected with 429 + Retry-After.
    with pytest.raises(HTTPException) as exc:
        await enforce_request_limit(
            redis, profile_id=pid, request_limit=3,
            request_limit_interval="1 day", operation="generate",
        )
    assert exc.value.status_code == 429
    assert exc.value.headers.get("Retry-After") == "86400"


@pytest.mark.asyncio
async def test_separate_operations_have_separate_windows():
    redis = _FakeRedis()
    pid = uuid4()
    for _ in range(2):
        await enforce_request_limit(
            redis, profile_id=pid, request_limit=2,
            request_limit_interval="1 day", operation="generate",
        )
    # A different operation label is a different bucket — still allowed.
    await enforce_request_limit(
        redis, profile_id=pid, request_limit=2,
        request_limit_interval="1 day", operation="grade",
    )


@pytest.mark.asyncio
async def test_fails_open_on_redis_error():
    redis = _FakeRedis(fail=True)
    # A counter outage must never block generation.
    await enforce_request_limit(
        redis, profile_id=uuid4(), request_limit=1,
        request_limit_interval="1 day", operation="generate",
    )


@pytest.mark.asyncio
async def test_rl_b2_ttl_armed_once_atomically_never_extended():
    """RL-B2: the INCR + arm-TTL is a single atomic ``eval``, so the TTL is
    armed exactly ONCE (on the first call) and a live window is never extended
    on later calls — no ~2x quota slide, and no lost-EXPIRE forever-429 (the
    EXPIRE can't be separated from the INCR)."""
    redis = _FakeRedis()
    pid = uuid4()
    for _ in range(3):
        await enforce_request_limit(
            redis, profile_id=pid, request_limit=5,
            request_limit_interval="1 day", operation="generate",
        )
    key = f"reqlimit:{pid}:generate"
    assert redis.expires[key] == 86400
    # Armed on the first call only — subsequent calls find a live TTL and
    # leave it untouched (the window-slide the old read-time re-arm caused).
    assert redis.arm_count == 1
