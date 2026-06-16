"""Internal handler: test_invocation_complete — canonical per-invocation completion.

Mirrors ``/attempt/chat/complete``. Pure data primitive: writes a
test_invocation_completion_entry row binding the invocation to a
freshly-minted call. Grading is a separate operation surfaced at
``/test/grade``.

Soft/accept (stage-inactive): ``soft=True`` writes the completion row dormant
(``active=False``) + a pending ``soft_calls_entry``; the ack activates it
(``activate_rows``) or rejects. The wrapper lives inside this internal impl, so
``operation_key`` is wired for the replay gate, ``group_id`` is resolved from the
invocation (so ``can_audit`` holds), and the wrapper's ``call_id`` is the soft key.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.activate.activate import activate_rows
from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestInvocationCompletePayload
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "test"
OPERATION = "invocation_complete"


class TestInvocationCompleteInternalResult(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    invocation_id: str
    completion_id: str | None = None
    success: bool = True
    idempotency_key: UUID | None = None


async def test_invocation_complete_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestInvocationCompleteInternalResult:
    """Mark a single invocation complete by writing its completion entry."""
    payload = TestInvocationCompletePayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_invocation_complete")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_invocation_complete")

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    async def _run(call_id: UUID | None = None) -> TestInvocationCompleteInternalResult:
        redis = get_redis_client()
        from app.infra.invocation.refresh import refresh_invocation_impl

        # ── Short-circuit: ack — activate / reject the staged completion ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending completion for this call.")
            ids = entry.patch or {}
            completion_id = ids.get("completion_id")
            if accept and completion_id:
                async with get_pool().acquire() as conn:
                    await activate_rows(conn, table="test_invocation_completion_entry", ids=[UUID(completion_id)])
                await refresh_invocation_impl(
                    get_pool(), redis,
                    profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
                    targets=["test_invocation_completion_mv"],
                )
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return TestInvocationCompleteInternalResult(
                invocation_id=str(payload.test_invocation_id),
                completion_id=completion_id,
                idempotency_key=idempotency_key,
            )

        from app.tools.entries.calls.create import create_call
        from app.tools.entries.groups.get import get_groups
        from app.tools.entries.runs.create import create_run
        from app.tools.entries.test_invocation.get import get_test_invocations
        from app.tools.entries.test_invocation_completion.create import (
            create_test_invocation_completion,
        )

        # ── Owner/role/department scope (BOLA + cross-dept guard, T2) ──────
        # The completion insert below is keyed solely by the caller-supplied
        # ``test_invocation_id``. Without this, any authenticated profile could
        # force-complete ANOTHER user's invocation (terminal-state corruption)
        # simply by passing their invocation id. Resolve invocation → owner and
        # route through the shared attempt-mutation gate.
        from app.infra.profile_identity_context import (
            resolve_profile_identity_context,
        )
        from app.infra.test.permissions import enforce_test_access_by_invocation

        requester = await resolve_profile_identity_context(
            get_pool(), UUID(str(profile_id)), redis,
        )
        await enforce_test_access_by_invocation(
            get_pool(), redis,
            invocation_id=payload.test_invocation_id, requester=requester,
        )

        async with get_pool().acquire() as conn:
            async with transaction_with_writeback(conn):
                invs = await get_test_invocations(conn, [payload.test_invocation_id], redis)
                if not invs:
                    raise ValueError(f"Invocation {payload.test_invocation_id} not found")
                group_id = invs[0].group_id
                if group_id is None:
                    raise ValueError(f"Invocation {payload.test_invocation_id} has no group_id")
                groups = await get_groups(conn, [group_id], redis)
                if not groups or groups[0].session_id is None:
                    raise ValueError(f"Group {group_id} has no session_id")
                run = await create_run(conn, redis, group_id=group_id, session_id=groups[0].session_id)
                call = await create_call(conn, redis, run_id=run.id, session_id=groups[0].session_id)
                completion = await create_test_invocation_completion(
                    conn, redis, invocation_id=payload.test_invocation_id, call_id=call.id, soft=soft,
                )
                if soft and call_id is not None:
                    await create_soft_call(
                        conn, redis, call_id=call_id, artifact=ARTIFACT,
                        operation=OPERATION, artifact_id=completion.id, status="pending",
                        patch={"completion_id": str(completion.id)},
                    )

        if not soft:
            await refresh_invocation_impl(
                get_pool(), redis,
                profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
                targets=["test_invocation_completion_mv"],
            )
        return TestInvocationCompleteInternalResult(
            invocation_id=str(payload.test_invocation_id),
            completion_id=str(completion.id),
            idempotency_key=call_id,
        )

    if not audit:
        return await _run()

    # Resolve the invocation's group up front so the wrapper can mint a
    # calls_entry (``can_audit`` needs group_id) + thread its call_id.
    redis = get_redis_client()
    from app.tools.entries.test_invocation.get import get_test_invocations
    async with get_pool().acquire() as conn:
        invs = await get_test_invocations(conn, [payload.test_invocation_id], redis)
    if not invs or invs[0].group_id is None:
        raise ValueError(f"Invocation {payload.test_invocation_id} not found or has no group_id")
    audit_group_id = invs[0].group_id

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        group_id=audit_group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestInvocationCompleteInternalResult,
    )
