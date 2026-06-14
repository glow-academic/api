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
    """Minimal async Redis fake supporting incr/expire with an optional fault."""

    def __init__(self, *, fail: bool = False) -> None:
        self._counts: dict[str, int] = {}
        self.expires: dict[str, int] = {}
        self._fail = fail

    async def incr(self, key: str) -> int:
        if self._fail:
            raise RuntimeError("redis down")
        self._counts[key] = self._counts.get(key, 0) + 1
        return self._counts[key]

    async def expire(self, key: str, ttl: int) -> None:
        self.expires[key] = ttl


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
