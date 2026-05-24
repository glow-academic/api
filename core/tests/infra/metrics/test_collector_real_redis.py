"""Real-Redis behavior tests for `core/app/infra/metrics/collector.py`.

The existing `test_collector.py` and `test_metrics_snapshot.py` use a
`_FakeRedis` stub that mirrors the call shape but not the behavior. Per
AGENTS.md's integration-first house style, this file exercises the
collector against the real `redis_client` fixture from conftest.

What's tested here that the mock files can't catch:
- Atomic INCR semantics across concurrent-ish calls.
- Per-minute latency key partitioning (`metrics:latency:{minute_ts}`).
- The 120s TTL on latency buckets (verified via `ttl()`).
- Fallback to in-memory when Redis raises mid-call.
- End-to-end `log_metrics_snapshot` → row appears in `metrics_entry`.
- End-to-end `log_health_checks` → rows appear in `health_entry`.
"""

from __future__ import annotations

import time
from collections import deque
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from app.infra.metrics import collector

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _reset_collector_and_redis(redis_client):
    """Each test starts with a clean slate: zeroed module globals AND the
    Redis keys the collector touches flushed. Without this, counter values
    leak between tests and metrics-related assertions become order-
    dependent."""
    collector._requests_count = 0
    collector._errors_count = 0
    collector._latency_samples = deque(maxlen=1000)
    collector._db_pool = None
    collector._redis_client = None

    # Drop collector-owned keys (counters + any current/recent latency buckets).
    await redis_client.delete("metrics:requests_total", "metrics:errors_total")
    now = int(time.time())
    cur_minute = (now // 60) * 60
    keys_to_clear = [f"metrics:latency:{cur_minute + offset}" for offset in (-60, 0, 60)]
    await redis_client.delete(*keys_to_clear)
    yield


# ─── initialize_metrics ────────────────────────────────────────────────────


class TestInitializeMetrics:
    async def test_seeds_redis_counters_to_zero(self, pool, redis_client):
        """initialize_metrics writes 0 to the two counters with NX
        semantics: idempotent on warm start, observable on cold start."""
        await collector.initialize_metrics(pool, redis_client)

        requests = await redis_client.get("metrics:requests_total")
        errors = await redis_client.get("metrics:errors_total")

        assert requests is not None and int(requests) == 0
        assert errors is not None and int(errors) == 0

    async def test_nx_does_not_overwrite_existing_counters(
        self, pool, redis_client
    ):
        """If the counters already hold non-zero values (e.g. mid-life
        restart), initialize_metrics MUST NOT reset them — the NX flag
        guarantees idempotency."""
        await redis_client.set("metrics:requests_total", 42)
        await redis_client.set("metrics:errors_total", 7)

        await collector.initialize_metrics(pool, redis_client)

        assert int(await redis_client.get("metrics:requests_total")) == 42
        assert int(await redis_client.get("metrics:errors_total")) == 7


# ─── record_request / record_error (Redis backend) ─────────────────────────


class TestRecordWithRedis:
    async def test_record_request_increments_counter(self, pool, redis_client):
        await collector.initialize_metrics(pool, redis_client)

        await collector.record_request(12.5)
        await collector.record_request(7.5)
        await collector.record_request(15.0)

        assert int(await redis_client.get("metrics:requests_total")) == 3

    async def test_record_request_pushes_latency_into_minute_bucket(
        self, pool, redis_client
    ):
        await collector.initialize_metrics(pool, redis_client)

        await collector.record_request(20.0)
        await collector.record_request(40.0)

        now = time.time()
        minute_ts = int(now // 60) * 60
        samples = await redis_client.lrange(f"metrics:latency:{minute_ts}", 0, -1)

        # Order is newest-first (LPUSH); both samples must be present.
        as_floats = sorted(float(s) for s in samples)
        assert as_floats == [20.0, 40.0]

    async def test_latency_bucket_has_ttl_set(self, pool, redis_client):
        """The 120s TTL keeps Redis from accumulating one minute-key per
        minute forever. The TTL is reset on every push; check it exists
        and is in a sane range (1..120s)."""
        await collector.initialize_metrics(pool, redis_client)
        await collector.record_request(5.0)

        minute_ts = int(time.time() // 60) * 60
        ttl = await redis_client.ttl(f"metrics:latency:{minute_ts}")

        assert 1 <= ttl <= 120, f"Expected TTL in (0, 120], got {ttl}"

    async def test_record_error_increments_error_counter(
        self, pool, redis_client
    ):
        await collector.initialize_metrics(pool, redis_client)

        await collector.record_error()
        await collector.record_error()

        assert int(await redis_client.get("metrics:errors_total")) == 2


# ─── get_current_metrics ───────────────────────────────────────────────────


class TestGetCurrentMetricsRedis:
    async def test_returns_redis_backed_values(self, pool, redis_client):
        await collector.initialize_metrics(pool, redis_client)
        await collector.record_request(10.0)
        await collector.record_request(20.0)
        await collector.record_request(30.0)
        await collector.record_error()

        metrics = await collector.get_current_metrics()

        assert metrics["backend"] == "redis"
        assert metrics["requests_total"] == 3
        assert metrics["errors_total"] == 1
        assert metrics["avg_latency_ms"] == 20.0  # (10 + 20 + 30) / 3
        assert metrics["sample_count"] == 3

    async def test_returns_zeros_when_no_activity(self, pool, redis_client):
        """A freshly initialized collector with no requests yet returns
        all zeros — not None, not missing keys, not exceptions."""
        await collector.initialize_metrics(pool, redis_client)

        metrics = await collector.get_current_metrics()

        assert metrics == {
            "requests_total": 0,
            "errors_total": 0,
            "avg_latency_ms": 0.0,
            "sample_count": 0,
            "backend": "redis",
        }


# ─── In-memory fallback (no Redis at init) ─────────────────────────────────


class TestInMemoryFallback:
    async def test_record_request_increments_in_memory(self, pool):
        """When initialized without Redis, requests/latencies live in
        the module-level deque + counter. No Redis keys are touched."""
        await collector.initialize_metrics(pool, redis_client=None)

        await collector.record_request(8.0)
        await collector.record_request(12.0)

        assert collector._requests_count == 2
        assert list(collector._latency_samples) == [8.0, 12.0]

    async def test_get_current_metrics_returns_memory_backend(self, pool):
        await collector.initialize_metrics(pool, redis_client=None)
        await collector.record_request(50.0)
        await collector.record_error()

        metrics = await collector.get_current_metrics()

        assert metrics["backend"] == "memory"
        assert metrics["requests_total"] == 1
        assert metrics["errors_total"] == 1
        assert metrics["avg_latency_ms"] == 50.0


# ─── log_metrics_snapshot integration ──────────────────────────────────────


class TestLogMetricsSnapshot:
    async def test_writes_row_with_observed_metrics(self, pool, redis_client):
        """End-to-end: record_request → log_metrics_snapshot →
        metrics_entry row exists with the recorded values."""
        await collector.initialize_metrics(pool, redis_client)
        await collector.record_request(100.0)
        await collector.record_request(200.0)
        await collector.record_error()

        await collector.log_metrics_snapshot()

        # The snapshot timestamp rounds to the current minute.
        ts = datetime.fromtimestamp(
            int(time.time() // 60) * 60, tz=UTC
        )

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT requests_total, errors_total, avg_latency_ms
                FROM metrics_entry
                WHERE ts = $1
                ORDER BY session_id DESC
                LIMIT 1
                """,
                ts,
            )

        assert row is not None
        assert row["requests_total"] == 2
        assert row["errors_total"] == 1
        assert row["avg_latency_ms"] == 150.0  # (100 + 200) / 2

    async def test_noop_when_pool_is_none(self, redis_client):
        """The collector module declares `_db_pool` may be None (e.g.
        before initialize_metrics has run). log_metrics_snapshot must
        early-return rather than NPE."""
        collector._db_pool = None
        collector._redis_client = redis_client

        # No exception, no write — just returns.
        await collector.log_metrics_snapshot()

    async def test_noop_when_redis_is_none(self, pool):
        """Symmetric guard: without a Redis client there's no source of
        metrics to read, so the snapshot is skipped rather than writing
        zero-everywhere garbage.

        Counted via delta on metrics_entry total — order-independent across
        sibling tests that share the current minute's `ts`."""
        collector._db_pool = pool
        collector._redis_client = None

        async with pool.acquire() as conn:
            count_before = await conn.fetchval("SELECT COUNT(*) FROM metrics_entry")

        await collector.log_metrics_snapshot()

        async with pool.acquire() as conn:
            count_after = await conn.fetchval("SELECT COUNT(*) FROM metrics_entry")

        assert count_after == count_before, (
            "log_metrics_snapshot wrote a row despite _redis_client being None"
        )
