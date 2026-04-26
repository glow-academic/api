"""Internal handler: test_start — canonical client-orchestrated entry.

Pure setup: creates a test_entry only. Mirrors attempt_start — does
NOT pre-create invocation rows. The client renders the benchmark's
invocation_entry templates and calls /test/invocation/create per card
to materialize a test_invocation_entry on demand.
"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.client_types import TestStartPayload
from app.infra.test.workflows import test_start_impl
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.websocket.test_types import TestErrorData


class TestStartInternalResult(BaseModel):
    test_id: str
    benchmark_id: str | None = None
    success: bool = True


async def test_start_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestStartInternalResult:
    """Run canonical test start. Returns when rows are written."""
    TestStartPayload(**data)  # validate inbound shape

    profile_id = data.get("profile_id")
    if not profile_id:
        raise ValueError("Missing profile_id for test_start")
    session_id = data.get("session_id")
    if not session_id:
        raise ValueError("Missing session_id for test_start")

    identity = await resolve_profile_identity_context(
        get_pool(),
        UUID(profile_id),
        get_redis_client(),
        session_id=UUID(session_id),
    )
    if not identity or not identity.profiles_id:
        raise ValueError("Profile context not found for test_start")

    async def _run() -> TestStartInternalResult:
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            downstream = emit or make_emit()
            await downstream(events)

        # Use a stable dict reference so test_start_impl's
        # ``data["_result"] = {...}`` write propagates back here.
        runner_data: dict[str, Any] = {
            **data,
            "profiles_id": str(identity.profiles_id),
        }

        await test_start_impl(
            runner_data,
            emit=_emit,
            pool=get_pool(),
            redis=get_redis_client(),
        )

        # test_start_impl is now setup-only. Any error propagates via
        # internal events; surface them as ValueError so the audit
        # framework writes a clean failed lifecycle event.
        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event.startswith("test.") and event.event.endswith(".error"):
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        # Workflow writes its handoff into runner_data["_result"]
        # (test_id + benchmark_id). Read it out.
        result = runner_data.get("_result") or {}
        return TestStartInternalResult(
            test_id=result.get("test_id", ""),
            benchmark_id=result.get("benchmark_id"),
        )

    if not audit:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(profile_id),
        operation="start",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(session_id),
        response_model=TestStartInternalResult,
    )
