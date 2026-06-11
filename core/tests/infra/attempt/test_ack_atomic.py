"""A3/A4 ack-atomicity tests for attempt complete / start.

A3 (concurrent double-ack TOCTOU): each ack now routes the terminal transition
through ``resolve_soft_call`` (atomic conditional INSERT). A second ack on an
already-resolved call gets ``None`` back → the impl SKIPS the activate side
effect (no double ack).

A4 (non-atomic accept): the impl wraps the ``resolve_soft_call`` ledger write +
the ``activate_rows`` side effect in ONE ``conn.transaction()`` and runs the MV
``refresh_*`` only AFTER that commit — so a crash can't leave rows active with a
stale 'pending' ledger, and the refresh never snapshots before its ledger row.

These are black-box: we monkeypatch the composed tools
(``get_soft_call`` / ``resolve_soft_call`` / ``activate_rows`` / ``refresh_*``)
at the impl module namespace and assert the call sequence — DB-free.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


# ── Fakes ──────────────────────────────────────────────────────────────────


class _FakeTx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        self._conn.tx_open = True
        self._conn.activate_inside_tx = []
        return None

    async def __aexit__(self, *a):
        self._conn.tx_open = False
        return False


class _FakeConn:
    def __init__(self):
        self.tx_open = False
        self.activate_inside_tx: list = []

    def transaction(self):
        return _FakeTx(self)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def execute(self, *a, **k):
        return None


class _FakePool:
    def __init__(self):
        self.conn = _FakeConn()

    def acquire(self):
        return self.conn


def _entry(operation):
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import UTC, datetime

    return GetSoftCallResponse(
        id=uuid4(),
        call_id=uuid4(),
        artifact="attempt",
        operation=operation,
        status="pending",
        artifact_id=uuid4(),
        patch={
            "completion_id": str(uuid4()),
            "attempt_id": str(uuid4()),
            "persona_id": str(uuid4()),
            "chat_id": str(uuid4()),
            "is_practice": False,
        },
        created_at=datetime.now(UTC),
    )


# ── complete.py ──────────────────────────────────────────────────────────────


def _wire_complete(monkeypatch, *, resolve_returns):
    import app.infra.attempt.complete as mod

    calls = {"activate": 0, "refresh": 0, "resolve_in_tx": []}
    pool = _FakePool()

    async def fake_get(conn, key, redis, **k):
        return _entry("complete")

    async def fake_resolve(conn, redis, **k):
        # Must run inside the caller's transaction (A4).
        calls["resolve_in_tx"].append(pool.conn.tx_open)
        return resolve_returns

    async def fake_activate(conn, **k):
        calls["activate"] += 1
        # Activation must run inside the same open transaction (A4).
        assert pool.conn.tx_open is True

    async def fake_refresh(p, redis, **k):
        calls["refresh"] += 1
        # Refresh must run AFTER the transaction closes (A4).
        assert pool.conn.tx_open is False

    monkeypatch.setattr(mod, "get_soft_call", fake_get)
    monkeypatch.setattr(mod, "resolve_soft_call", fake_resolve)
    monkeypatch.setattr(mod, "activate_rows", fake_activate)
    monkeypatch.setattr(mod, "refresh_attempt_impl", fake_refresh)
    return mod, pool, calls


async def test_complete_first_ack_activates(monkeypatch):
    """First ack: resolve returns an entry → activate + refresh run once."""
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import UTC, datetime

    won = GetSoftCallResponse(
        id=uuid4(), call_id=uuid4(), artifact="attempt", operation="complete",
        status="accepted", artifact_id=uuid4(), patch=None,
        created_at=datetime.now(UTC),
    )
    mod, pool, calls = _wire_complete(monkeypatch, resolve_returns=won)

    await mod.complete_attempt_impl(
        pool, object(), profile_id=uuid4(), session_id=uuid4(),
        accept=True, idempotency_key=uuid4(),
    )
    assert calls["activate"] == 1
    assert calls["refresh"] == 1
    assert calls["resolve_in_tx"] == [True]  # resolve ran inside the txn


async def test_complete_double_ack_skips_side_effect(monkeypatch):
    """Concurrent double-ack: resolve returns None (already resolved) → the
    impl SKIPS activate AND refresh (no double side effect)."""
    mod, pool, calls = _wire_complete(monkeypatch, resolve_returns=None)

    result = await mod.complete_attempt_impl(
        pool, object(), profile_id=uuid4(), session_id=uuid4(),
        accept=True, idempotency_key=uuid4(),
    )
    assert calls["activate"] == 0
    assert calls["refresh"] == 0
    assert result["success"] is True  # idempotent — still reports success


async def test_complete_reject_does_not_activate(monkeypatch):
    """Reject (accept=False): resolve writes a 'rejected' terminal row but no
    activation/refresh happens."""
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import UTC, datetime

    won = GetSoftCallResponse(
        id=uuid4(), call_id=uuid4(), artifact="attempt", operation="complete",
        status="rejected", artifact_id=uuid4(), patch=None,
        created_at=datetime.now(UTC),
    )
    mod, pool, calls = _wire_complete(monkeypatch, resolve_returns=won)

    await mod.complete_attempt_impl(
        pool, object(), profile_id=uuid4(), session_id=uuid4(),
        accept=False, idempotency_key=uuid4(),
    )
    assert calls["activate"] == 0
    assert calls["refresh"] == 0
    assert calls["resolve_in_tx"] == [True]


# ── start.py ─────────────────────────────────────────────────────────────────


def _wire_start(monkeypatch, *, resolve_returns):
    import app.infra.attempt.start as mod

    calls = {"activate": 0, "refresh": 0, "resolve_in_tx": []}
    pool = _FakePool()

    async def fake_identity(p, pid, redis, **k):
        from app.infra.profile_identity_context import ProfileIdentityContext

        return ProfileIdentityContext(
            profiles_id=uuid4(), name="a", role="member", role_name="member",
            role_description="", role_artifacts=[], primary_email=None, emails=[],
            primary_department_id=None, department_ids=[], settings_id=None,
            request_limit=None, request_limit_interval=None, is_active=True,
            role_level=1,
            role_permissions=[("attempt", "start")],
        )

    async def fake_get(conn, key, redis, **k):
        return _entry("start")

    async def fake_resolve(conn, redis, **k):
        calls["resolve_in_tx"].append(pool.conn.tx_open)
        return resolve_returns

    async def fake_activate(conn, **k):
        calls["activate"] += 1
        assert pool.conn.tx_open is True

    async def fake_refresh(p, redis, **k):
        calls["refresh"] += 1
        assert pool.conn.tx_open is False

    monkeypatch.setattr(mod, "resolve_profile_identity_context", fake_identity)
    monkeypatch.setattr(mod, "get_soft_call", fake_get)
    monkeypatch.setattr(mod, "resolve_soft_call", fake_resolve)
    monkeypatch.setattr(mod, "activate_rows", fake_activate)
    # refresh_attempt_impl is imported lazily inside the impl; patch the source.
    import app.infra.attempt.refresh as refresh_mod
    monkeypatch.setattr(refresh_mod, "refresh_attempt_impl", fake_refresh)
    return mod, pool, calls


def _start_request():
    from app.infra.attempt.start import AttemptStartRequest

    return AttemptStartRequest(idempotency_key=uuid4(), accept=True)


async def test_start_first_ack_activates(monkeypatch):
    """First ack: resolve returns an entry → persona+attempt activations run
    (2 activate_rows calls) inside the txn, refresh after."""
    from app.tools.entries.soft_calls.types import GetSoftCallResponse
    from datetime import UTC, datetime

    won = GetSoftCallResponse(
        id=uuid4(), call_id=uuid4(), artifact="attempt", operation="start",
        status="accepted", artifact_id=uuid4(), patch=None,
        created_at=datetime.now(UTC),
    )
    mod, pool, calls = _wire_start(monkeypatch, resolve_returns=won)
    req = _start_request()

    await mod.attempt_start_impl(
        pool, object(), profile_id=uuid4(), session_id=uuid4(),
        request=req, accept=True, idempotency_key=req.idempotency_key,
    )
    assert calls["activate"] == 2  # personas_entry + attempt_entry
    assert calls["refresh"] == 1
    assert calls["resolve_in_tx"] == [True]


async def test_start_double_ack_skips_side_effect(monkeypatch):
    """Concurrent double-ack: resolve returns None → no activations, no refresh."""
    mod, pool, calls = _wire_start(monkeypatch, resolve_returns=None)
    req = _start_request()

    await mod.attempt_start_impl(
        pool, object(), profile_id=uuid4(), session_id=uuid4(),
        request=req, accept=True, idempotency_key=req.idempotency_key,
    )
    assert calls["activate"] == 0
    assert calls["refresh"] == 0
