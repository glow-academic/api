from __future__ import annotations

from collections import deque
from types import SimpleNamespace

import pytest

from app.infra.metrics import collector


class _FakeRedis:
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
    collector._requests_count = 0
    collector._errors_count = 0
    collector._latency_samples = deque(maxlen=1000)
    collector._db_pool = None
    collector._redis_client = None


@pytest.mark.asyncio
async def test_record_request_and_error_use_memory_fallback():
    await collector.record_request(12.5)
    await collector.record_request(7.5)
    await collector.record_error()

    metrics = await collector.get_current_metrics()

    assert metrics == {
        "requests_total": 2,
        "errors_total": 1,
        "avg_latency_ms": 10.0,
        "sample_count": 2,
        "backend": "memory",
    }


@pytest.mark.asyncio
async def test_initialize_metrics_and_record_request_use_redis_backend():
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


@pytest.mark.asyncio
async def test_log_metrics_snapshot_writes_aggregated_snapshot(monkeypatch):
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

    async def _write_metrics_snapshot(pool, **kwargs):
        captured["pool"] = pool
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


@pytest.mark.asyncio
async def test_log_health_checks_writes_service_results(monkeypatch):
    await collector.initialize_metrics(object(), None)

    checks = [{"service": "redis", "ok": True}]
    captured = {}

    async def _run_service_checks():
        return checks

    async def _write_health_checks(pool, **kwargs):
        captured["pool"] = pool
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
