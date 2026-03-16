"""Internal handler: test_start — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.test.client_types import TestStartPayload
from app.infra.test.proceed import test_proceed_internal_impl
from app.infra.test.workflows import test_start_impl
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.websocket.test_types import TestErrorData


class TestStartInternalResult(BaseModel):
    test_id: str
    invocation_id: str | None = None
    success: bool = True


async def test_start_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestStartInternalResult:
    """Run canonical test start orchestration for any surface."""
    payload = TestStartPayload(**data)
    del payload

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
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="start",
            emit=emit or make_emit(),
        )
        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await test_start_impl(
            {
                **data,
                "profiles_id": str(identity.profiles_id),
            },
            emit=_emit,
            pool=get_pool(),
            redis=get_redis_client(),
        )

        proceed_events = [
            event
            for event in recorded
            if event.bus == "internal" and event.event == "test_proceed"
        ]
        created_test_id = (
            proceed_events[0].data.get("test_id", "") if proceed_events else ""
        )
        if created_test_id and not data.get("sid"):
            return TestStartInternalResult(test_id=created_test_id)
        for event in proceed_events:
            try:
                await test_proceed_internal_impl(event.data, emit=_emit)
            except ValueError:
                # Creating the test itself is still a meaningful synchronous result.
                # Some flows populate invocation context asynchronously after start.
                if created_test_id:
                    return TestStartInternalResult(test_id=created_test_id)
                raise

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "test_started":
                return TestStartInternalResult(
                    test_id=event.data.get("test_id", ""),
                    invocation_id=event.data.get("invocation_entry_id"),
                )
            if event.event == "test_invocation_started":
                return TestStartInternalResult(
                    test_id=event.data.get("test_id", ""),
                    invocation_id=event.data.get("test_invocation_id"),
                )
            if event.event == "test_ended":
                return TestStartInternalResult(
                    test_id=event.data.get("test_id", ""),
                    success=bool(event.data.get("success", True)),
                )
            if event.event == "test_error":
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        if created_test_id:
            return TestStartInternalResult(test_id=created_test_id)

        raise ValueError("Test start completed without a terminal event")

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
