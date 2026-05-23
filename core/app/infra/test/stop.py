"""Internal handler: test_stop — canonical orchestration entry.

Soft/accept (record-and-hold): test stop is signal-based — ``_run`` emits a
``test.stop.completed`` event (no DB row to stage). So ``soft=True`` records a
pending ``soft_calls_entry`` WITHOUT emitting (stages the intent); the ack
({idempotency_key, accept}) emits the stop (accept) or discards it (reject).
``soft=False`` emits immediately (original behavior). Mirrors ``stop_attempt_impl``.
The wrapper lives inside this internal impl, so ``operation_key`` is wired for the
replay gate and the wrapper's ``call_id`` is threaded in as the soft-ledger key.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestStopPayload
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "test"
OPERATION = "stop"


class TestStopInternalResult(BaseModel):
    invocation_id: str
    success: bool
    message: str | None = None
    idempotency_key: UUID | None = None


async def test_stop_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestStopInternalResult:
    """Run canonical test stop orchestration for any surface."""
    payload = TestStopPayload(**data)
    sid = data.get("sid")
    profile_id_val = data.get("profile_id")

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    async def _emit_stop() -> None:
        rooms: list[str] = [f"test_{payload.invocation_id}"]
        if profile_id_val:
            rooms.append(str(profile_id_val))
        downstream_emit = emit or make_emit()
        await downstream_emit(
            [
                SocketEvent(
                    bus="internal",
                    event="test.stop.completed",
                    data={
                        "sid": sid,
                        "rooms": rooms,
                        "invocation_id": str(payload.invocation_id),
                        "success": True,
                        "message": "Test execution stopped",
                    },
                )
            ]
        )

    async def _run(call_id: UUID | None = None) -> TestStopInternalResult:
        # ── Short-circuit: ack — emit (accept) or discard (reject) the staged stop ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, get_redis_client(), artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending stop for this call.")
            if accept:
                await _emit_stop()
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, get_redis_client(), call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return TestStopInternalResult(
                invocation_id=str(payload.invocation_id),
                success=True,
                message="Test execution stopped" if accept else "Stop discarded",
                idempotency_key=idempotency_key,
            )

        # ── Soft propose: record intent without emitting ──
        if soft and call_id is not None:
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, get_redis_client(), call_id=call_id, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=payload.invocation_id, status="pending",
                    patch={"invocation_id": str(payload.invocation_id)},
                )
            return TestStopInternalResult(
                invocation_id=str(payload.invocation_id),
                success=True,
                message="Test stop staged",
                idempotency_key=call_id,
            )

        # ── Live: emit the stop now ──
        await _emit_stop()
        return TestStopInternalResult(
            invocation_id=str(payload.invocation_id),
            success=True,
            message="Test execution stopped",
            idempotency_key=call_id,
        )

    if not audit:
        return await _run()

    profile_id = data.get("profile_id")
    session_id = data.get("session_id")
    if not profile_id or not session_id:
        return await _run()

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(str(session_id)),
        entity_id=payload.invocation_id,
        response_model=TestStopInternalResult,
    )
