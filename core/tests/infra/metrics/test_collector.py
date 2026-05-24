"""Tests for metrics collector — in-memory fallback, Redis backend, snapshots."""

from collections import deque
from types import SimpleNamespace

import pytest

from app.infra.metrics import collector

pytestmark = pytest.mark.asyncio


class _FakeRedis:
    """Minimal async Redis stub for unit-testing the collector."""

    def __init__(self):
        self.values: dict[str, str | int] = {}
        self.lists: dict[str, list[str]] = {}

    async def set(self, key, value, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    async def lpush(self, key, value):
        self.lists.setdefault(key, []).insert(0, value)

    async def expire(self, key, ttl):
        return True

    async def lrange(self, key, start, stop):
        return list(self.lists.get(key, []))


@pytest.fixture(autouse=True)
def _reset_collector_state():
    """Reset module-level collector state before every test."""
    collector._requests_count = 0
    collector._errors_count = 0
    collector._latency_samples = deque(maxlen=1000)
    collector._db_pool = None
    collector._redis_client = None


# -- in-memory fallback --------------------------------------------------------


async def test_record_request_and_error_use_memory_fallback():
    """Without Redis, metrics are tracked in module-level counters."""
    await collector.record_request(12.5)
    await collector.record_request(7.5)
    await collector.record_error()

    metrics = await collector.get_current_metrics()

    assert metrics["requests_total"] == 2
    assert metrics["errors_total"] == 1
    assert metrics["avg_latency_ms"] == 10.0
    assert metrics["sample_count"] == 2
    assert metrics["backend"] == "memory"


async def test_get_current_metrics_returns_zeros_when_empty():
    """Fresh collector reports all zeros with memory backend."""
    metrics = await collector.get_current_metrics()

    assert metrics["requests_total"] == 0
    assert metrics["errors_total"] == 0
    assert metrics["avg_latency_ms"] == 0.0
    assert metrics["sample_count"] == 0
    assert metrics["backend"] == "memory"


# -- Redis backend -------------------------------------------------------------


async def test_initialize_and_record_via_redis():
    """With Redis, metrics flow through atomic Redis operations."""
    redis = _FakeRedis()

    await collector.initialize_metrics(object(), redis)
    await collector.record_request(15.0)
    await collector.record_error()

    metrics = await collector.get_current_metrics()

    assert metrics["backend"] == "redis"
    assert metrics["requests_total"] == 1
    assert metrics["errors_total"] == 1
    assert metrics["sample_count"] == 1
    assert metrics["avg_latency_ms"] == 15.0


async def test_redis_failure_falls_back_to_memory():
    """When Redis raises, record_request/record_error fall back to in-memory."""

    class _BrokenRedis(_FakeRedis):
        async def incr(self, key):
            raise ConnectionError("Redis down")

        async def lpush(self, key, value):
            raise ConnectionError("Redis down")

    redis = _BrokenRedis()
    await collector.initialize_metrics(object(), redis)

    await collector.record_request(5.0)
    await collector.record_error()

    # In-memory counters should have the data
    assert collector._requests_count == 1
    assert collector._errors_count == 1


# -- log_metrics_snapshot ------------------------------------------------------


async def test_log_metrics_snapshot_skips_when_no_pool():
    """log_metrics_snapshot is a no-op when _db_pool is None."""
    collector._db_pool = None
    # Should not raise
    await collector.log_metrics_snapshot()


async def test_log_metrics_snapshot_writes_aggregated_data(monkeypatch):
    """log_metrics_snapshot reads from Redis and writes to write_metrics_snapshot."""
    redis = _FakeRedis()
    await collector.initialize_metrics(object(), redis)

    monkeypatch.setattr(collector.time, "time", lambda: 120.0)
    await collector.record_request(10.0)
    await collector.record_request(20.0)
    await collector.record_error()

    monkeypatch.setattr(collector.psutil, "cpu_percent", lambda interval=0.1: 42.0)
    monkeypatch.setattr(
        collector.psutil,
        "Process",
        lambda: SimpleNamespace(
            memory_info=lambda: SimpleNamespace(rss=123456),
        ),
    )

    captured = {}

    async def _write_metrics_snapshot(pool, redis, **kwargs):
        captured["pool"] = pool
        captured["redis"] = redis
        captured["kwargs"] = kwargs

    monkeypatch.setattr(
        "app.infra.metrics_snapshot.write_metrics_snapshot",
        _write_metrics_snapshot,
    )

    await collector.log_metrics_snapshot()

    assert captured["pool"] is collector._db_pool
    assert captured["kwargs"]["requests_total"] == 2
    assert captured["kwargs"]["errors_total"] == 1
    assert captured["kwargs"]["avg_latency_ms"] == 15.0
    assert captured["kwargs"]["cpu_percent"] == 42.0
    assert captured["kwargs"]["memory_bytes"] == 123456


# -- log_health_checks ---------------------------------------------------------


async def test_log_health_checks_skips_when_no_pool():
    """log_health_checks is a no-op when _db_pool is None."""
    collector._db_pool = None
    await collector.log_health_checks()


async def test_log_health_checks_delegates_to_writers(monkeypatch):
    """log_health_checks calls run_service_checks and write_health_checks."""
    await collector.initialize_metrics(object(), _FakeRedis())

    checks = [{"service": "redis", "ok": True}]
    captured = {}

    async def _run_service_checks():
        return checks

    async def _write_health_checks(pool, redis, **kwargs):
        captured["pool"] = pool
        captured["redis"] = redis
        captured["kwargs"] = kwargs

    monkeypatch.setattr(collector.time, "time", lambda: 180.0)
    monkeypatch.setattr(
        "app.infra.health.checks.run_service_checks",
        _run_service_checks,
    )
    monkeypatch.setattr(
        "app.infra.metrics_snapshot.write_health_checks",
        _write_health_checks,
    )

    await collector.log_health_checks()

    assert captured["pool"] is collector._db_pool
    assert captured["kwargs"]["checks"] == checks
