"""DEP-A: /readyz gates on real DB+Redis dependency health (not a pre-DB 401).

The blue-green readiness gate used to probe an authed route with no token and
accept the 401 (raised before any dependency is touched). /readyz instead pings
the dependencies a real request needs, so a broken-DB/Redis color is caught
before it swaps to live. DB+Redis are hard-gated (503); Keycloak is reported
but NOT gated (known deploy-time warmup races would stall every deploy).
"""

from __future__ import annotations

import json

import pytest

import app.infra.health.checks as checks
from app.infra.health.checks import ServiceCheckResult
from app.server import readyz

pytestmark = pytest.mark.asyncio


def _ok(latency: float = 1.0) -> ServiceCheckResult:
    return ServiceCheckResult(True, latency)


def _bad(err: str) -> ServiceCheckResult:
    return ServiceCheckResult(False, 0.0, err)


def _patch(monkeypatch, *, db, redis, kc):
    async def _db(_pool):
        return db

    async def _redis(_client):
        return redis

    async def _kc():
        return kc

    monkeypatch.setattr(checks, "check_database", _db)
    monkeypatch.setattr(checks, "check_redis", _redis)
    monkeypatch.setattr(checks, "check_keycloak", _kc)


async def test_ready_when_db_and_redis_ok(monkeypatch):
    _patch(monkeypatch, db=_ok(), redis=_ok(), kc=_ok())
    resp = await readyz()
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body))["ready"] is True


async def test_not_ready_when_db_down(monkeypatch):
    _patch(monkeypatch, db=_bad("connection refused"), redis=_ok(), kc=_ok())
    resp = await readyz()
    assert resp.status_code == 503
    body = json.loads(bytes(resp.body))
    assert body["ready"] is False
    assert body["checks"]["database"]["ok"] is False


async def test_not_ready_when_redis_down(monkeypatch):
    _patch(monkeypatch, db=_ok(), redis=_bad("redis down"), kc=_ok())
    resp = await readyz()
    assert resp.status_code == 503


async def test_keycloak_down_is_reported_but_not_gated(monkeypatch):
    # The whole point: a KC blip must NOT block the swap (DB+Redis are up).
    _patch(monkeypatch, db=_ok(), redis=_ok(), kc=_bad("keycloak unreachable"))
    resp = await readyz()
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    assert body["ready"] is True
    assert body["checks"]["keycloak"]["ok"] is False
    assert body["checks"]["keycloak"]["gated"] is False
