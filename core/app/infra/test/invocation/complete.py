"""Internal handler: test_invocation_complete — canonical per-invocation completion.

Mirrors ``/attempt/chat/complete``. Pure data primitive: writes a
test_invocation_completion_entry row binding the invocation to a
freshly-minted call. Grading is a separate operation surfaced at
``/test/grade``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestInvocationCompletePayload
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn


class TestInvocationCompleteInternalResult(BaseModel):
    invocation_id: str
    completion_id: str | None = None
    success: bool = True


async def test_invocation_complete_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestInvocationCompleteInternalResult:
    """Mark a single invocation complete by writing its completion entry."""
    redis = get_redis_client()
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

    async def _run() -> TestInvocationCompleteInternalResult:
        redis = get_redis_client()
        from app.infra.invocation.refresh import refresh_invocation_impl
        from app.tools.entries.calls.create import create_call
        from app.tools.entries.groups.get import get_groups
        from app.tools.entries.runs.create import create_run
        from app.tools.entries.test_invocation.get import get_test_invocations
        from app.tools.entries.test_invocation_completion.create import (
            create_test_invocation_completion,
        )

        async with get_pool().acquire() as conn:
            invs = await get_test_invocations(
                conn, [payload.test_invocation_id], redis, bypass_mv=True,
            )
            if not invs:
                raise ValueError(
                    f"Invocation {payload.test_invocation_id} not found"
                )
            inv = invs[0]
            group_id = inv.group_id
            if group_id is None:
                raise ValueError(
                    f"Invocation {payload.test_invocation_id} has no group_id"
                )
            groups = await get_groups(conn, [group_id], redis)
            if not groups or groups[0].session_id is None:
                raise ValueError(
                    f"Group {group_id} has no session_id"
                )
            run = await create_run(
                conn, redis, group_id=group_id, session_id=groups[0].session_id,
            )
            call = await create_call(
                conn, redis, run_id=run.id, session_id=groups[0].session_id,
            )
            completion = await create_test_invocation_completion(
                conn, redis,
                invocation_id=payload.test_invocation_id,
                call_id=call.id,
            )

        await refresh_invocation_impl(
            get_pool(), redis,
            profile_id=UUID(str(profile_id)),
            session_id=UUID(str(session_id)),
            targets=["test_invocation_completion_mv"],
        )

        return TestInvocationCompleteInternalResult(
            invocation_id=str(payload.test_invocation_id),
            completion_id=str(completion.id),
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="invocation_complete",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestInvocationCompleteInternalResult,
    )
