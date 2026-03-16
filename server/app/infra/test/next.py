"""Internal handler: test_next — canonical orchestration entry."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.client_types import TestNextPayload
from app.infra.test.group import test_group_internal_impl
from app.infra.test.run import test_run_internal_impl
from app.infra.test.workflows import test_next_impl
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.websocket.test_types import TestErrorData
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class TestNextInternalResult(BaseModel):
    invocation_id: str
    run_id: str
    current_run: int = 1
    total_runs: int = 1


async def test_next_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestNextInternalResult:
    """Run canonical test next orchestration for any surface."""
    payload = TestNextPayload(**data)

    pool = get_pool()
    if not pool:
        raise ValueError("Database pool not initialized")

    async def _run() -> TestNextInternalResult:
        downstream_emit = emit or make_emit()
        recorded: list[SocketEvent] = []
        workflow_sid = data.get("sid") or f"http-test-next:{data.get('session_id')}"

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            await downstream_emit(events)

        await test_next_impl(
            {
                **data,
                "sid": workflow_sid,
            },
            emit=_emit,
            pool=pool,
        )

        group_events = [
            event
            for event in recorded
            if event.bus == "internal" and event.event == "test_group"
        ]
        for event in group_events:
            await test_group_internal_impl(event.data, emit=_emit)

        run_events = [
            event
            for event in recorded
            if event.bus == "internal" and event.event == "test_run"
        ]
        for event in run_events:
            result = await test_run_internal_impl(
                {
                    **event.data,
                    "session_id": data.get("session_id"),
                    "profile_id": data.get("profile_id"),
                },
                emit=_emit,
                audit=False,
            )
            return TestNextInternalResult(
                invocation_id=result.invocation_id,
                run_id=result.run_id,
                current_run=1,
                total_runs=1,
            )

        for event in recorded:
            if event.bus != "internal":
                continue
            if event.event == "test_error":
                error = TestErrorData(**event.data)
                raise ValueError(error.message)

        raise ValueError("No pending test run found")

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
        operation="next",
        runner=_run,
        arguments=build_audit_arguments(data),
        session_id=UUID(str(session_id)),
        test_id=payload.test_id,
        response_model=TestNextInternalResult,
    )
