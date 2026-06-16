"""A2 regression tests for the idempotency replay gate in audit.py.

Two HIGH bugs are covered:

  • The in-flight lock (``idem:op:<key>``) was taken but NEVER released — it had
    no delete anywhere. For a ``can_audit=False`` op (no registered tool, or
    missing session/group/profiles_id) NO ``calls_entry`` receipt is written, so
    the lock was the only trace. Result: a retry within the 300s TTL 409'd
    ("already in progress") for an op that had already SUCCEEDED, and a retry
    after the TTL re-executed the side effect (duplicate write).

  • Replay correctness must not depend on ``can_audit``. The fix releases the
    lock after execution AND writes a lightweight Redis receipt on the
    non-audit path so a retry replays the stored result.

These run the real ``run_artifact_operation_with_audit`` with its DB/socket/
tool-resolution deps mocked (deps-as-params via monkeypatch) and a fake Redis
that records lock/receipt key state.
"""

from __future__ import annotations

import json
import logging
from uuid import uuid4

import pytest

from app.infra.events import audit as audit_mod
from app.infra.events.audit import (
    _IDEM_LOCK_PREFIX,
    _IDEM_RECEIPT_PREFIX,
    run_artifact_operation_with_audit,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRedis:
    """Minimal async Redis recording get/set(nx)/delete on a dict."""

    def __init__(self):
        self.store: dict[str, str] = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, *, nx=False, ex=None):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def delete(self, *keys):
        n = 0
        for k in keys:
            if k in self.store:
                del self.store[k]
                n += 1
        return n

    async def expire(self, key, ttl):
        return True


class _FakeConn:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


class _FakePool:
    def acquire(self):
        return _FakeConn()


class _SilentSio:
    async def emit(self, *a, **kw):
        return None


class _FakeProfile:
    def __init__(self, profiles_id, session_id):
        self.profiles_id = profiles_id
        self.session_id = session_id


class _FakeCommon:
    def __init__(self, profile):
        self.profile = profile


def _wire_common_deps(monkeypatch, *, with_tool: bool):
    """Mock the shared deps. ``with_tool`` controls can_audit:
    a resolved tool + session + profiles_id ⇒ can_audit=True.
    """
    profiles_id = uuid4()
    session_id = uuid4()

    async def mock_common(pool, redis, **kw):
        return _FakeCommon(_FakeProfile(profiles_id, session_id))

    async def mock_resolve_tool(conn, redis, *, artifact, operation):
        if not with_tool:
            return None

        class _RT:
            tool_id = uuid4()
            instruction_template = None

        return _RT()

    monkeypatch.setattr(audit_mod, "resolve_common_context", mock_common)
    monkeypatch.setattr(
        "app.infra.tools.resolve_for_operation.resolve_tool_for_operation",
        mock_resolve_tool,
    )
    monkeypatch.setattr(audit_mod, "internal_sio", _SilentSio())

    # get_soft_call (completed-emit ledger lookup) — best-effort, return None.
    async def mock_get_soft_call(conn, call_id, redis, *, artifact=None):
        return None

    monkeypatch.setattr(
        "app.tools.entries.soft_calls.get.get_soft_call", mock_get_soft_call
    )
    return session_id


# ---------------------------------------------------------------------------
# A2 — non-audit path: lock released + replay via redis receipt
# ---------------------------------------------------------------------------


async def test_non_audit_op_releases_lock_and_replays_on_retry(monkeypatch):
    """can_audit=False op: lock is released after success, and an immediate
    retry replays the stored result instead of re-executing (no duplicate,
    no stuck-lock 409)."""
    _wire_common_deps(monkeypatch, with_tool=False)

    # No prior calls_entry receipt ever exists for the non-audit path.
    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()
    op_key = uuid4()
    runs = {"count": 0}

    async def runner():
        runs["count"] += 1
        return {"success": True, "value": runs["count"]}

    args = {"foo": "bar"}

    first = await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments=args, operation_key=op_key,
    )
    assert first == {"success": True, "value": 1}
    assert runs["count"] == 1

    # Lock must be gone (released in the success path).
    assert f"{_IDEM_LOCK_PREFIX}{op_key}" not in redis.store
    # A redis replay receipt must exist.
    assert f"{_IDEM_RECEIPT_PREFIX}{op_key}" in redis.store

    # Retry within TTL: must REPLAY, not re-execute.
    second = await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments=args, operation_key=op_key,
    )
    assert second == {"success": True, "value": 1}
    assert runs["count"] == 1, "retry must replay, not re-run the side effect"


async def test_non_audit_op_failure_releases_lock(monkeypatch):
    """A failed non-audit op must release the lock (no receipt cached for
    errors) so the retry is free to truly re-run."""
    _wire_common_deps(monkeypatch, with_tool=False)

    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()
    op_key = uuid4()

    async def boom():
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        await run_artifact_operation_with_audit(
            pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
            runner=boom, arguments={"x": 1}, operation_key=op_key,
        )

    assert f"{_IDEM_LOCK_PREFIX}{op_key}" not in redis.store
    # No success receipt for a failure.
    assert f"{_IDEM_RECEIPT_PREFIX}{op_key}" not in redis.store


async def test_non_audit_op_same_key_different_body_is_409(monkeypatch):
    """A retry reusing the key with a DIFFERENT payload must 409 off the
    redis receipt, not silently replay the first result."""
    from fastapi import HTTPException

    _wire_common_deps(monkeypatch, with_tool=False)

    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()
    op_key = uuid4()

    async def runner():
        return {"success": True}

    await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments={"a": 1}, operation_key=op_key,
    )

    with pytest.raises(HTTPException) as exc:
        await run_artifact_operation_with_audit(
            pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
            runner=runner, arguments={"a": 2}, operation_key=op_key,
        )
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# A2 — audit path: receipt-based replay still dedups (unchanged behavior)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# O3 — best-effort receipt-timing update failure must be VISIBLE (WARNING),
#      not swallowed at debug. This write IS the "lifecycle finished" signal,
#      so a systematic failure (disk full / perms / missing receipt) silently
#      degrading the forensic trail used to be invisible.
# ---------------------------------------------------------------------------


class _FakeAuditResult:
    """Stands in for create_tool_call's return — audit.py reads only these."""

    def __init__(self, *, result, call_upload_id):
        self.result = result
        self.call_upload_id = call_upload_id
        self.error = None
        self.call_id = call_upload_id


async def test_o3_receipt_timing_failure_logs_warning(monkeypatch, tmp_path, caplog):
    """The final receipt-timing merge fails (the receipt file doesn't exist at
    the upload folder), and that failure must surface as a WARNING naming the
    call_upload_id — not a silent debug line."""
    _wire_common_deps(monkeypatch, with_tool=True)

    call_upload_id = uuid4()

    # No prior calls_entry receipt → no replay; the runner executes.
    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    # Mock create_tool_call to return success + a call_upload_id WITHOUT writing
    # any receipt file. The final timing-merge block then tries to read
    # ``{upload_folder}/call/{call_upload_id}.json`` which does not exist →
    # FileNotFoundError → the elevated WARNING.
    async def mock_create_tool_call(pool, redis, **kw):
        return _FakeAuditResult(
            result={"success": True, "value": "ok"},
            call_upload_id=call_upload_id,
        )

    monkeypatch.setattr(audit_mod, "create_tool_call", mock_create_tool_call)

    # Tool-wire resolution hits the DB; stub it (no tool_payload needed here).
    async def mock_get_tools(pool, ids, redis):
        return []

    monkeypatch.setattr(audit_mod, "get_tools", mock_get_tools)

    redis = _FakeRedis()
    pool = _FakePool()

    async def runner():
        return {"success": True, "value": "ok"}

    with caplog.at_level(logging.DEBUG, logger="app.infra.events.audit"):
        result = await run_artifact_operation_with_audit(
            pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
            runner=runner, arguments={"foo": "bar"}, operation_key=uuid4(),
            upload_folder=tmp_path, group_id=uuid4(),
        )

    # The op still SUCCEEDS (receipt-timing write is best-effort) ...
    assert result == {"success": True, "value": "ok"}
    # ... but the failure to record timings is now VISIBLE at WARNING.
    timing_warnings = [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "receipt timing update failed" in r.getMessage()
    ]
    assert timing_warnings, "receipt-timing failure must log at WARNING"
    assert str(call_upload_id) in timing_warnings[0].getMessage()


async def test_o3_receipt_timing_success_does_not_warn(monkeypatch, tmp_path, caplog):
    """Control: when the receipt file exists the timing merge succeeds and emits
    no failure WARNING."""
    _wire_common_deps(monkeypatch, with_tool=True)

    call_upload_id = uuid4()

    # Stage the receipt file so the timing-merge read/write succeeds.
    (tmp_path / "call").mkdir(parents=True, exist_ok=True)
    (tmp_path / "call" / f"{call_upload_id}.json").write_text(
        json.dumps({"arguments": {"foo": "bar"}}), encoding="utf-8"
    )

    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    async def mock_create_tool_call(pool, redis, **kw):
        return _FakeAuditResult(
            result={"success": True, "value": "ok"},
            call_upload_id=call_upload_id,
        )

    monkeypatch.setattr(audit_mod, "create_tool_call", mock_create_tool_call)

    async def mock_get_tools(pool, ids, redis):
        return []

    monkeypatch.setattr(audit_mod, "get_tools", mock_get_tools)

    redis = _FakeRedis()
    pool = _FakePool()

    async def runner():
        return {"success": True, "value": "ok"}

    with caplog.at_level(logging.DEBUG, logger="app.infra.events.audit"):
        await run_artifact_operation_with_audit(
            pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
            runner=runner, arguments={"foo": "bar"}, operation_key=uuid4(),
            upload_folder=tmp_path, group_id=uuid4(),
        )

    assert not [
        r for r in caplog.records
        if r.levelno == logging.WARNING
        and "receipt timing update failed" in r.getMessage()
    ]


async def test_audit_path_replays_from_calls_entry_receipt(monkeypatch, tmp_path):
    """can_audit=True: a prior completed call's persisted receipt short-circuits
    a retry — the runner is NOT re-invoked. The A2 fix must not break this."""
    _wire_common_deps(monkeypatch, with_tool=True)

    op_key = uuid4()
    runs = {"count": 0}

    # Stage a persisted receipt on disk that search_calls will point at.
    receipt_rel = "call/replayed.json"
    (tmp_path / "call").mkdir(parents=True, exist_ok=True)
    (tmp_path / receipt_rel).write_text(
        json.dumps(
            {
                "arguments": {"foo": "bar"},
                "raw_output": {"success": True, "value": "from_receipt"},
            }
        ),
        encoding="utf-8",
    )

    class _PriorCall:
        id = uuid4()
        file_path = receipt_rel

    async def mock_search_calls(conn, redis, **kw):
        return [_PriorCall()]

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()

    async def runner():
        runs["count"] += 1
        return {"success": True, "value": "fresh"}

    result = await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments={"foo": "bar"}, operation_key=op_key,
        upload_folder=tmp_path,
    )

    assert result == {"success": True, "value": "from_receipt"}
    assert runs["count"] == 0, "replay must not re-invoke the runner"
    # No lock should linger from a replayed call.
    assert f"{_IDEM_LOCK_PREFIX}{op_key}" not in redis.store


# ---------------------------------------------------------------------------
# AU2 — can_audit=True replay must survive the fire-and-forget audit-persist
#       window. ``_persist_audit_writes`` (create_tool_call) writes the receipt
#       file/junction that supplies ``file_path`` in the BACKGROUND and is not
#       awaited, but the lock is released synchronously. A retry landing before
#       the persist commits finds the call with file_path=None (filtered out)
#       and must replay from the Redis receipt — which is now written on EVERY
#       success, not just can_audit=False — instead of re-executing.
# ---------------------------------------------------------------------------


async def test_audit_path_replays_via_redis_receipt_before_filepath_durable(
    monkeypatch, tmp_path
):
    op_key = uuid4()
    execs = {"count": 0}
    search_calls_seen = {"n": 0}

    _wire_common_deps(monkeypatch, with_tool=True)

    async def mock_create_tool_call(pool, redis, **kw):
        # A real execution goes through the audit store. The background persist
        # that would set file_path is NOT simulated → file_path stays None.
        execs["count"] += 1
        return _FakeAuditResult(
            result={"success": True, "value": "first"},
            call_upload_id=uuid4(),
        )

    monkeypatch.setattr(audit_mod, "create_tool_call", mock_create_tool_call)

    async def mock_get_tools(pool, ids, redis):
        return []

    monkeypatch.setattr(audit_mod, "get_tools", mock_get_tools)

    class _PriorCallNoFile:
        id = uuid4()
        file_path = None  # background persist hasn't landed yet

    async def mock_search_calls(conn, redis, **kw):
        search_calls_seen["n"] += 1
        # First run: nothing yet. Retry: the calls_entry row is visible but its
        # file_path is still NULL (persist in flight).
        return [] if search_calls_seen["n"] == 1 else [_PriorCallNoFile()]

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()
    args = {"foo": "bar"}

    async def runner():
        return {"success": True, "value": "first"}

    first = await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments=args, operation_key=op_key,
        upload_folder=tmp_path, group_id=uuid4(),
    )
    assert first == {"success": True, "value": "first"}
    assert execs["count"] == 1
    # AU2 fix: a Redis replay receipt is written even on the audited path.
    assert f"{_IDEM_RECEIPT_PREFIX}{op_key}" in redis.store

    # Retry while file_path is still NULL: must REPLAY from the redis receipt,
    # not re-execute through the audit store.
    second = await run_artifact_operation_with_audit(
        pool, redis, artifact="auth", profile_id=uuid4(), operation="update",
        runner=runner, arguments=args, operation_key=op_key,
        upload_folder=tmp_path, group_id=uuid4(),
    )
    assert second == {"success": True, "value": "first"}
    assert execs["count"] == 1, (
        "retry in the audit-persist window must replay via the redis receipt, "
        "not re-execute"
    )


# ---------------------------------------------------------------------------
# A3 — a soft/propose op must NOT have a replayable success receipt: its
#      "success" is only a DORMANT staged binding, which a later ack may reject.
#      Replaying it would re-assert a creation that was since rejected.
# ---------------------------------------------------------------------------


async def test_soft_propose_non_audit_does_not_cache_success_receipt(monkeypatch):
    """A soft propose on the non-audit path must NOT leave a redis replay
    receipt, and a retry must RE-RUN (re-propose) rather than replay a stale
    success that a since-issued reject would have invalidated."""
    _wire_common_deps(monkeypatch, with_tool=False)

    async def mock_search_calls(conn, redis, **kw):
        return []

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    redis = _FakeRedis()
    pool = _FakePool()
    op_key = uuid4()
    runs = {"count": 0}

    async def runner():
        runs["count"] += 1
        return {"success": True, "value": runs["count"]}

    args = {"soft": True, "foo": "bar"}

    first = await run_artifact_operation_with_audit(
        pool, redis, artifact="test", profile_id=uuid4(), operation="run",
        runner=runner, arguments=args, operation_key=op_key,
    )
    assert first == {"success": True, "value": 1}
    # A3: no replayable success receipt is cached for a soft/propose.
    assert f"{_IDEM_RECEIPT_PREFIX}{op_key}" not in redis.store

    # Retry: must re-run (re-propose), NOT replay the stale "success".
    second = await run_artifact_operation_with_audit(
        pool, redis, artifact="test", profile_id=uuid4(), operation="run",
        runner=runner, arguments=args, operation_key=op_key,
    )
    assert runs["count"] == 2, "soft propose retry must re-run, not replay success"
    assert second == {"success": True, "value": 2}


async def test_soft_propose_audit_path_does_not_replay_success(monkeypatch, tmp_path):
    """A soft propose whose calls_entry receipt says success=True must NOT be
    replayed — the runner re-runs so the soft-call ledger stays authoritative
    (a since-issued reject can't be papered over by a cached success)."""
    _wire_common_deps(monkeypatch, with_tool=True)

    op_key = uuid4()
    runs = {"count": 0}

    receipt_rel = "call/soft_replayed.json"
    (tmp_path / "call").mkdir(parents=True, exist_ok=True)
    (tmp_path / receipt_rel).write_text(
        json.dumps(
            {
                "arguments": {"soft": True, "foo": "bar"},
                "raw_output": {"success": True, "value": "from_receipt"},
            }
        ),
        encoding="utf-8",
    )

    class _PriorCall:
        id = uuid4()
        file_path = receipt_rel

    async def mock_search_calls(conn, redis, **kw):
        return [_PriorCall()]

    monkeypatch.setattr(audit_mod, "search_calls", mock_search_calls)

    async def mock_create_tool_call(pool, redis, **kw):
        # The audit store wraps + invokes the runner internally; mark that the
        # store path (i.e. a true re-run, NOT a replay) was reached.
        runs["store_invoked"] = True
        return _FakeAuditResult(
            result={"success": True, "value": "fresh"},
            call_upload_id=uuid4(),
        )

    monkeypatch.setattr(audit_mod, "create_tool_call", mock_create_tool_call)

    async def mock_get_tools(pool, ids, redis):
        return []

    monkeypatch.setattr(audit_mod, "get_tools", mock_get_tools)

    redis = _FakeRedis()
    pool = _FakePool()

    async def runner():
        runs["count"] += 1
        return {"success": True, "value": "fresh"}

    result = await run_artifact_operation_with_audit(
        pool, redis, artifact="test", profile_id=uuid4(), operation="run",
        runner=runner, arguments={"soft": True, "foo": "bar"}, operation_key=op_key,
        upload_folder=tmp_path, group_id=uuid4(),
    )

    # A3: the cached success receipt MUST NOT be replayed for a soft propose —
    # control falls through to the audit store (a real re-run), not the
    # "from_receipt" short-circuit.
    assert result != {"success": True, "value": "from_receipt"}
    assert runs.get("store_invoked") is True, (
        "soft propose must fall through to a re-run, not replay the cached success"
    )
