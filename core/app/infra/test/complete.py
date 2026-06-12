"""Internal handler: test_complete — canonical whole-test completion.

Mirrors AttemptComplete on the test side. Pure data primitive: marks
every uncompleted invocation on the test as completed by inserting a
test_invocation_completion_entry row. No orchestration, no LLM call.

Soft/accept (stage-inactive, bulk): ``soft=True`` writes every completion row
dormant (``active=False``) + a pending ``soft_calls_entry`` whose ``patch`` holds
the completion ids; the ack ({idempotency_key, accept}) activates them all or
rejects. ``soft=False`` completes immediately. The wrapper lives inside this
internal impl, so ``operation_key`` is wired for the replay gate and the wrapper's
``call_id`` is threaded into the runner as the soft-ledger key.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.activate.activate import activate_rows
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestCompletePayload
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "test"
OPERATION = "complete"


class TestCompleteInternalResult(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_id: str
    success: bool = True
    completed_count: int = 0
    idempotency_key: UUID | None = None


async def _mark_all_invocations_complete(
    conn: asyncpg.Connection, test_id: UUID, *, soft: bool = False
) -> tuple[int, list[UUID]]:
    """For every uncompleted invocation on the test, write a completion
    entry. Returns ``(count, completion_ids)``. When ``soft`` the rows are
    written dormant (``active=False``) for the ack to activate."""
    redis = get_redis_client()
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.test_invocation.search import (
        search_test_invocation_entries_internal,
    )
    from app.tools.entries.test_invocation_completion.create import (
        create_test_invocation_completion,
    )

    invs, _total = await search_test_invocation_entries_internal(
        conn, redis, test_ids=[test_id], limit=1000,
    )

    from app.tools.entries.groups.get import get_groups

    # Atomic (A4): the bulk completion of all N invocations must be
    # all-or-nothing — each invocation mints run+call+completion (3 writes), and
    # a failure on the k-th invocation must not leave 1..k-1 committed-complete
    # with the k-th half-built (orphan run/call, no completion). All writes are
    # DB-only (redis write-backs are local cache pushes, not external/LLM calls),
    # so a single transaction around the loop is correct.
    completion_ids: list[UUID] = []
    async with conn.transaction():
        for inv in invs:
            if inv.invocation_completed:
                continue
            if inv.group_id is None:
                continue
            # Need a call_id for the completion record. Mint a fresh run+call
            # in the invocation's group, like the legacy proceed path did.
            groups = await get_groups(conn, [inv.group_id], redis)
            if not groups or groups[0].session_id is None:
                continue
            session_id = groups[0].session_id
            run = await create_run(conn, redis, group_id=inv.group_id, session_id=session_id)
            call = await create_call(conn, redis, run_id=run.id, session_id=session_id)
            completion = await create_test_invocation_completion(
                conn, redis, invocation_id=inv.invocation_id, call_id=call.id, soft=soft,
            )
            completion_ids.append(completion.id)

    return len(completion_ids), completion_ids


async def test_complete_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestCompleteInternalResult:
    """Mark every uncompleted invocation on the test as completed."""
    payload = TestCompletePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_complete")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_complete")

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    async def _run(call_id: UUID | None = None) -> TestCompleteInternalResult:
        from app.infra.invocation.refresh import refresh_invocation_impl

        # ── Short-circuit: ack — activate / reject the staged completion set ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, get_redis_client(), artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending completion for this call.")
            ids = entry.patch or {}
            completion_ids = [UUID(x) for x in ids.get("completion_ids", [])]
            if accept and completion_ids:
                async with get_pool().acquire() as conn:
                    await activate_rows(conn, table="test_invocation_completion_entry", ids=completion_ids)
                await refresh_invocation_impl(
                    get_pool(), get_redis_client(),
                    profile_id=UUID(str(profile_id)),
                    session_id=UUID(str(session_id)),
                    targets=["test_invocation_completion_mv"],
                )
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, get_redis_client(), call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return TestCompleteInternalResult(
                test_id=str(payload.test_id),
                completed_count=int(ids.get("completed_count", 0)),
                idempotency_key=idempotency_key,
            )

        # ── Owner/role/department scope (BOLA + cross-dept guard, T5) ──────
        # ``_mark_all_invocations_complete`` completes EVERY invocation on the
        # caller-supplied ``test_id``. Without this, any authenticated profile
        # could force-complete ANOTHER user's entire test. Resolve
        # ``test → owner`` and route through the shared attempt-mutation gate.
        from app.infra.profile_identity_context import (
            resolve_profile_identity_context,
        )
        from app.infra.test.permissions import enforce_test_access_by_test

        requester = await resolve_profile_identity_context(
            get_pool(), UUID(str(profile_id)), get_redis_client(),
        )
        await enforce_test_access_by_test(
            get_pool(), get_redis_client(),
            test_id=payload.test_id, requester=requester,
        )

        with timed("db_write"):
            async with get_pool().acquire() as conn:
                count, completion_ids = await _mark_all_invocations_complete(
                    conn, payload.test_id, soft=soft,
                )
                if soft and call_id is not None and completion_ids:
                    await create_soft_call(
                        conn, get_redis_client(), call_id=call_id, artifact=ARTIFACT,
                        operation=OPERATION, artifact_id=completion_ids[0], status="pending",
                        patch={
                            "completion_ids": [str(x) for x in completion_ids],
                            "completed_count": count,
                        },
                    )
        if count and not soft:
            with timed("refresh"):
                await refresh_invocation_impl(
                    get_pool(), get_redis_client(),
                    profile_id=UUID(str(profile_id)),
                    session_id=UUID(str(session_id)),
                    targets=["test_invocation_completion_mv"],
                )
        return TestCompleteInternalResult(
            test_id=str(payload.test_id), completed_count=count,
            idempotency_key=call_id,
        )

    if not audit:
        return await _run()

    # Resolve the time-windowed test group — the wrapper only mints a
    # calls_entry (which the soft ledger + call_id threading need) when
    # group_id/session/profile/tool are all present (``can_audit``).
    from app.infra.test.group import group_test_impl
    group_result = await group_test_impl(
        get_pool(), get_redis_client(),
        profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
        id_only=True,
    )

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(str(session_id)),
        entity_id=payload.test_id,
        test_id=payload.test_id,
        response_model=TestCompleteInternalResult,
    )
