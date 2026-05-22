"""Internal handler: test_run — canonical binding-row creator.

Pure data primitive. Mirrors /attempt/chat/message — writes a row,
nothing else. Bundle config + actual model invocation live elsewhere
(/test/invocation/trace seeds the bundle on a test_invocation_traces_entry, then
/test/generate executes the model and produces the run_id we bind here).
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
from app.infra.test.client_types import TestRunPayload
from app.infra.websocket.find_profile_by_socket import find_profile_by_socket
from app.infra.websocket.find_session_by_socket import find_session_by_socket
from app.infra.websocket.socket_event import EmitFn
from app.infra.invocation.refresh import refresh_invocation_impl
from app.infra.server_timing import timed
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)


class TestRunInternalResult(BaseModel):
    test_invocation_run_id: str
    success: bool = True


async def test_run_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestRunInternalResult:
    """Insert a test_invocation_runs_entry binding row."""
    redis = get_redis_client()
    payload = TestRunPayload(**data)
    sid = data.get("sid", "")

    profile_id = data.get("profile_id") or (
        await find_profile_by_socket(sid) if sid else None
    )
    if not profile_id:
        raise ValueError("Missing profile_id for test_run")

    session_id = data.get("session_id") or (
        await find_session_by_socket(sid) if sid else None
    )
    if not session_id:
        raise ValueError("Missing session_id for test_run")

    async def _run() -> TestRunInternalResult:
        redis = get_redis_client()
        with timed("db_write"):
            async with get_pool().acquire() as conn:
                result = await create_test_invocation_runs(
                    conn, redis,
                    test_invocation_id=payload.test_invocation_id,
                    run_id=payload.run_id,
                    test_invocation_traces_id=payload.test_invocation_trace_id,
                )
        with timed("refresh"):
            await refresh_invocation_impl(
                get_pool(), redis,
                profile_id=UUID(str(profile_id)),
                session_id=UUID(str(session_id)),
                targets=["test_invocation_runs_mv"],
            )
        return TestRunInternalResult(
            test_invocation_run_id=str(result.id),
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="run",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestRunInternalResult,
    )
