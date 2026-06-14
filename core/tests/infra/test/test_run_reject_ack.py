"""A1: a soft-call REJECT ack must not look like a successful commit.

The ack short-circuit in ``test_run_internal_impl._run`` previously returned
``TestRunInternalResult`` with ``success`` defaulting to True on BOTH accept and
reject, so the audit wrapper's ``test.run.completed`` payload was
indistinguishable from an accepted binding. These tests pin the reject branch to
``success=False`` (and accept to ``success=True``).
"""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

pytestmark = pytest.mark.asyncio


def _fake_pool():
    """A pool whose ``.acquire()`` yields a no-op async connection.

    The connection's ``.transaction()`` is an async context manager so the
    A2 reject branch (delete + ledger write in one txn) can run unmocked.
    """
    conn = MagicMock()

    @asynccontextmanager
    async def _txn():
        yield None

    conn.transaction = lambda: _txn()

    @asynccontextmanager
    async def _acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = lambda: _acquire()
    return pool


def _pending_entry(idem_key, run_row_id):
    from app.tools.entries.soft_calls.types import GetSoftCallResponse

    return GetSoftCallResponse(
        id=uuid4(),
        call_id=idem_key,
        artifact="test",
        operation="run",
        status="pending",
        artifact_id=run_row_id,
        patch={"test_invocation_run_id": str(run_row_id)},
        created_at=datetime.now(timezone.utc),
    )


async def _invoke_ack(*, accept: bool, return_delete_mock: bool = False):
    """Drive the ack short-circuit of test_run_internal_impl (audit=False)."""
    from app.infra.test import run as run_mod

    idem_key = uuid4()
    run_row_id = uuid4()
    profile_id = uuid4()
    session_id = uuid4()

    delete_mock = AsyncMock(return_value=[run_row_id])
    with patch.object(run_mod, "get_pool", lambda: _fake_pool()), \
         patch.object(run_mod, "get_redis_client", lambda: MagicMock()), \
         patch.object(run_mod, "get_soft_call", AsyncMock(return_value=_pending_entry(idem_key, run_row_id))), \
         patch.object(run_mod, "create_soft_call", AsyncMock()), \
         patch.object(run_mod, "activate_rows", AsyncMock()), \
         patch.object(run_mod, "delete_artifacts", delete_mock), \
         patch.object(run_mod, "refresh_invocation_impl", AsyncMock()):
        result = await run_mod.test_run_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                "soft": True,
                "accept": accept,
                "idempotency_key": str(idem_key),
                # payload fields (TestRunPayload) — present but unused by the ack branch
                "test_id": str(uuid4()),
                "test_invocation_id": str(uuid4()),
                "run_id": str(uuid4()),
                "test_invocation_trace_id": str(uuid4()),
            },
            audit=False,
        )
    if return_delete_mock:
        return result, delete_mock, run_row_id
    return result


async def test_reject_ack_carries_success_false():
    """A reject ack (accept=False) must report success=False, not the default True."""
    result = await _invoke_ack(accept=False)
    assert result.success is False


async def test_accept_ack_carries_success_true():
    """An accept ack stays success=True (the fix is scoped to the reject branch)."""
    result = await _invoke_ack(accept=True)
    assert result.success is True


# A2: a reject must clean up the dormant (active=False) binding row so it can't
# leak forever or be resurrected into the live MV by a later stray activate.
async def test_reject_ack_deletes_dormant_row():
    """A reject ack hard-deletes the dormant binding row (same txn as the ledger)."""
    _result, delete_mock, run_row_id = await _invoke_ack(
        accept=False, return_delete_mock=True
    )
    delete_mock.assert_awaited_once()
    _, kwargs = delete_mock.await_args
    assert kwargs["table"] == "test_invocation_runs_entry"
    assert kwargs["ids"] == [run_row_id]


async def test_accept_ack_does_not_delete_row():
    """An accept ack activates — it must NOT delete the binding row."""
    _result, delete_mock, _run_row_id = await _invoke_ack(
        accept=True, return_delete_mock=True
    )
    delete_mock.assert_not_awaited()
