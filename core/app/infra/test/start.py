"""Internal handler: test_start — canonical client-orchestrated entry.

Pure setup: creates a test_entry only. Mirrors attempt_start — does
NOT pre-create test_invocation_entry rows. Returns {test_id,
invocation_id, benchmark_id} where invocation_id is the FIRST
benchmark invocation_entry template (the row the client will route
into), exactly as attempt_start returns {attempt_id, chat_id} where
chat_id is the parent's first chat_entry template. The client's
useTestStart hands off to useTestRoute → useTestGenerate, which fires
/test/generate so the LLM materializes the test_invocation_entry.

Soft/accept (stage-inactive): ``soft=True`` creates the test_entry +
benchmark_test junction dormant (``active=False``) + a pending ``soft_calls_entry``;
the ack ({idempotency_key, accept}) activates them (test_entry by id, the junction
by test_id since it has no id column) or rejects. Mirrors attempt_start's staging.
The wrapper lives inside this internal impl, so ``operation_key`` is wired for the
replay gate and the wrapper's ``call_id`` is threaded into the workflow as the
soft-ledger key.
"""

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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.test.client_types import TestStartPayload
from app.infra.test.workflows import test_start_impl
from app.infra.websocket.socket_event import EmitFn, SocketEvent, make_emit
from app.infra.websocket.test_types import TestErrorData
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "test"
OPERATION = "start"


class TestStartInternalResult(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_id: str
    invocation_id: str | None = None
    benchmark_id: str | None = None
    success: bool = True
    idempotency_key: UUID | None = None


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

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    with timed("profile"):
        identity = await resolve_profile_identity_context(
            get_pool(),
            UUID(profile_id),
            get_redis_client(),
            session_id=UUID(session_id),
        )
    if not identity or not identity.profiles_id:
        raise ValueError("Profile context not found for test_start")

    async def _run(call_id: UUID | None = None) -> TestStartInternalResult:
        # ── Short-circuit: ack — activate / reject the staged test ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, get_redis_client(), artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending test start for this call.")
            ids = entry.patch or {}
            if accept:
                async with get_pool().acquire() as conn:
                    async with transaction_with_writeback(conn):
                        await activate_rows(conn, table="test_entry", ids=[UUID(ids["test_id"])])
                        # benchmark_test_entry has no id column → activate by test_id
                        if ids.get("benchmark_id"):
                            await conn.execute(
                                "UPDATE benchmark_test_entry SET active = true WHERE test_id = $1",
                                UUID(ids["test_id"]),
                            )
                from app.infra.invocation.refresh import refresh_invocation_impl
                from app.infra.test.refresh import refresh_test_impl
                await refresh_test_impl(
                    get_pool(), get_redis_client(),
                    profile_id=UUID(profile_id), session_id=UUID(session_id),
                    targets=["test_mv"],
                )
                await refresh_invocation_impl(
                    get_pool(), get_redis_client(),
                    profile_id=UUID(profile_id), session_id=UUID(session_id),
                    targets=["test_invocation_mv"],
                )
            async with get_pool().acquire() as conn:
                await create_soft_call(
                    conn, get_redis_client(), call_id=idempotency_key, artifact=ARTIFACT,
                    operation=OPERATION, artifact_id=entry.artifact_id,
                    status="accepted" if accept else "rejected",
                )
            return TestStartInternalResult(
                test_id=str(ids.get("test_id", "")),
                invocation_id=ids.get("invocation_id"),
                benchmark_id=ids.get("benchmark_id"),
                idempotency_key=idempotency_key,
            )

        recorded: list[SocketEvent] = []

        async def _emit(events: list[SocketEvent]) -> None:
            recorded.extend(events)
            downstream = emit or make_emit()
            await downstream(events)

        # Use a stable dict reference so test_start_impl's
        # ``data["_result"] = {...}`` write propagates back here. Thread
        # ``soft`` + the wrapper ``call_id`` so the workflow can stage the
        # dormant test + stash the soft_call keyed by the server call_id.
        runner_data: dict[str, Any] = {
            **data,
            "profiles_id": str(identity.profiles_id),
            "soft": soft,
            "call_id": str(call_id) if call_id is not None else None,
        }

        with timed("db_write"):
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
        # (test_id + invocation_id + benchmark_id). Read it out.
        result = runner_data.get("_result") or {}
        return TestStartInternalResult(
            test_id=result.get("test_id", ""),
            invocation_id=result.get("invocation_id"),
            benchmark_id=result.get("benchmark_id"),
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
        profile_id=UUID(profile_id), session_id=UUID(session_id),
        id_only=True,
    )

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(profile_id),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        session_id=UUID(session_id),
        response_model=TestStartInternalResult,
    )
