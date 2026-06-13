"""A2 — ``create_invocation_impl`` writes run + call + invocation (+ up to 8
junction tables) atomically.

The impl mints a run, a call, and a ``test_invocation_entry`` — the latter
inserting the parent row PLUS up to eight junction tables in a loop. Pre-fix
these autocommitted, so a bad FK mid-junction-loop materialized an invocation
with PARTIAL junctions (some models/rubrics linked, others missing) plus an
orphan run/call, while the write-back cache already advertised the full bundle.
The fix wraps run + call + invocation in one ``conn.transaction()`` (mirrors
chat_create).

Deps are stubbed as black boxes over a transaction-spy connection.
"""
from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

import app.infra.invocation.create as inv_mod
from app.infra.invocation.create import (
    CreateInvocationApiRequest,
    create_invocation_impl,
)
from tests.infra._txn_fakes import TxnSpyConn, TxnSpyPool

pytestmark = pytest.mark.asyncio


def _patch_preamble(monkeypatch):
    async def _resolve_identity(pool, profile_id, redis, *, session_id):
        return SimpleNamespace(profiles_id=uuid4(), role_permissions={})

    def _has_permission(perms, artifact, op):
        return True

    async def _resolve_group(pool, redis, **kwargs):
        return SimpleNamespace(group_id=uuid4())

    async def _get_tests(conn, ids, redis):
        return [SimpleNamespace(id=ids[0])]

    async def _get_groups(conn, ids, redis):
        return [SimpleNamespace(session_id=uuid4())]

    async def _refresh(pool, redis, **kwargs):
        return None

    # The F5 ownership guard (``enforce_test_access_by_test``) is exercised in
    # the authz-class suite; here it's a black box stubbed to allow so this
    # suite stays focused on transaction atomicity.
    async def _enforce_ok(pool, redis, *, test_id, requester, **kwargs):
        return None

    monkeypatch.setattr(inv_mod, "resolve_profile_identity_context", _resolve_identity)
    monkeypatch.setattr(inv_mod, "has_permission", _has_permission)
    monkeypatch.setattr(
        "app.infra.group.resolve.resolve_group_impl", _resolve_group
    )
    monkeypatch.setattr(inv_mod, "get_tests", _get_tests)
    monkeypatch.setattr(inv_mod, "get_groups", _get_groups)
    monkeypatch.setattr(inv_mod, "enforce_test_access_by_test", _enforce_ok)
    monkeypatch.setattr(inv_mod, "refresh_invocation_impl", _refresh)


async def test_invocation_write_failure_rolls_back_run_and_call(monkeypatch):
    """Fail the invocation (+junctions) write — the already-written run and call
    must be inside the same transaction so they roll back (no orphan run/call,
    no partial junctions)."""
    _patch_preamble(monkeypatch)
    conn = TxnSpyConn()
    writes: list = []

    async def _create_run(conn, redis, *, group_id, session_id):
        writes.append(("run", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, redis, *, run_id, session_id):
        writes.append(("call", conn.in_txn))
        return SimpleNamespace(id=uuid4())

    async def _create_invocation(conn, redis, **kwargs):
        # Stands in for the parent + 8-junction insert that can fail mid-loop.
        raise RuntimeError("injected junction-loop failure")

    monkeypatch.setattr(inv_mod, "create_run", _create_run)
    monkeypatch.setattr(inv_mod, "create_call", _create_call)
    monkeypatch.setattr(inv_mod, "create_test_invocation", _create_invocation)

    with pytest.raises(RuntimeError, match="injected junction-loop failure"):
        await create_invocation_impl(
            TxnSpyPool(conn),
            redis=object(),
            profile_id=uuid4(),
            session_id=uuid4(),
            request=CreateInvocationApiRequest(test_id=uuid4()),
        )

    assert writes == [("run", True), ("call", True)]  # both inside the txn
    assert conn.txn_entered is True
    assert conn.txn_exit_exc is RuntimeError  # txn unwound → run/call roll back


async def test_invocation_happy_path_commits_in_one_transaction(monkeypatch):
    _patch_preamble(monkeypatch)
    conn = TxnSpyConn()
    seen: dict[str, bool] = {}

    async def _create_run(conn, redis, *, group_id, session_id):
        seen["run"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    async def _create_call(conn, redis, *, run_id, session_id):
        seen["call"] = conn.in_txn
        return SimpleNamespace(id=uuid4())

    new_id = uuid4()

    async def _create_invocation(conn, redis, **kwargs):
        seen["invocation"] = conn.in_txn
        return SimpleNamespace(id=new_id)

    monkeypatch.setattr(inv_mod, "create_run", _create_run)
    monkeypatch.setattr(inv_mod, "create_call", _create_call)
    monkeypatch.setattr(inv_mod, "create_test_invocation", _create_invocation)

    result = await create_invocation_impl(
        TxnSpyPool(conn),
        redis=object(),
        profile_id=uuid4(),
        session_id=uuid4(),
        request=CreateInvocationApiRequest(test_id=uuid4()),
    )

    assert result.invocation_id == new_id
    assert seen == {"run": True, "call": True, "invocation": True}
    assert conn.txn_exit_exc is None
