"""Internal handler: test_complete — canonical whole-test completion.

Mirrors AttemptComplete on the test side. Pure data primitive: marks
every uncompleted invocation on the test as completed by inserting a
test_invocation_completion_entry row. No orchestration, no LLM call.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import asyncpg
from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestCompletePayload
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn


class TestCompleteInternalResult(BaseModel):
    test_id: str
    success: bool = True
    completed_count: int = 0


async def _mark_all_invocations_complete(
    conn: asyncpg.Connection, test_id: UUID
) -> int:
    """For every uncompleted invocation on the test, write a completion
    entry. Returns the count of newly-completed invocations."""
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.runs.create import create_run
    from app.tools.entries.test_invocation.search import (
        search_test_invocation_entries_internal,
    )
    from app.tools.entries.test_invocation_completion.create import (
        create_test_invocation_completion,
    )
    from app.tools.entries.test_invocation_completion.refresh import (
        refresh_test_invocation_completion,
    )

    invs, _total = await search_test_invocation_entries_internal(
        conn, test_ids=[test_id], limit=1000, bypass_mv=True,
    )

    count = 0
    for inv in invs:
        if inv.invocation_completed:
            continue
        if inv.group_id is None:
            continue
        # Need a call_id for the completion record. Mint a fresh run+call
        # in the invocation's group, like the legacy proceed path did.
        from app.tools.entries.groups.get import get_groups
        groups = await get_groups(conn, [inv.group_id])
        if not groups or groups[0].session_id is None:
            continue
        session_id = groups[0].session_id
        run = await create_run(conn, group_id=inv.group_id, session_id=session_id)
        call = await create_call(conn, run_id=run.id, session_id=session_id)
        await create_test_invocation_completion(
            conn, invocation_id=inv.invocation_id, call_id=call.id,
        )
        count += 1

    if count:
        await refresh_test_invocation_completion(conn)
    return count


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

    async def _run() -> TestCompleteInternalResult:
        async with get_pool().acquire() as conn:
            count = await _mark_all_invocations_complete(conn, payload.test_id)
        return TestCompleteInternalResult(
            test_id=str(payload.test_id), completed_count=count,
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="complete",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_id,
        test_id=payload.test_id,
        response_model=TestCompleteInternalResult,
    )
