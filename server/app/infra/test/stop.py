"""Internal handler: test_stop — canonical orchestration entry."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.stream.socket_bridge import wrap_emit_with_stream_bridge
from app.infra.test.client_types import TestStopPayload
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit


class TestStopInternalResult(BaseModel):
    invocation_id: str
    success: bool
    message: str | None = None


async def test_stop_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestStopInternalResult:
    """Run canonical test stop orchestration for any surface."""
    payload = TestStopPayload(**data)
    sid = data.get("sid")

    async def _run() -> TestStopInternalResult:
        result = TestStopInternalResult(
            invocation_id=str(payload.invocation_id),
            success=True,
            message="Test execution stopped",
        )
        downstream_emit = wrap_emit_with_stream_bridge(
            artifact="test",
            operation="stop",
            emit=emit or make_emit(),
            entity_id=payload.invocation_id,
        )
        await downstream_emit(
            [
                SocketEvent(
                    bus="internal",
                    event="test_stopped",
                    data={
                        "sid": sid,
                        "rooms": [sid, f"test_{payload.invocation_id}"] if sid else [],
                        "invocation_id": str(payload.invocation_id),
                        "success": True,
                        "message": result.message,
                    },
                )
            ]
        )
        return result

    if not audit:
        return await _run()

    profile_id = data.get("profile_id")
    session_id = data.get("session_id")
    if not profile_id or not session_id:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact="test",
        profile_id=UUID(str(profile_id)),
        operation="stop",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        entity_id=payload.invocation_id,
        response_model=TestStopInternalResult,
    )
