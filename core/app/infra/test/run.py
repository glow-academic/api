"""Internal handler: test_run — canonical binding-row creator.

Pure data primitive. Mirrors /attempt/chat/message — writes a row,
nothing else. Bundle config + actual model invocation live elsewhere
(/test/invocation/trace seeds the bundle on a test_invocation_traces_entry, then
/test/generate executes the model and produces the run_id we bind here).

Soft/accept (stage-inactive): ``soft=True`` writes the binding row dormant
(``active=False``) + a pending ``soft_calls_entry``; the ack
({idempotency_key, accept}) activates it (``activate_rows``) or rejects.
The wrapper lives inside this internal impl, so ``operation_key`` is wired for
the replay gate and the wrapper's ``call_id`` is threaded in as the soft-ledger key.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException
from pydantic import BaseModel

from app.infra.activate.activate import activate_rows
from app.infra.delete.delete_artifact import delete_artifacts
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
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.test_invocation_runs.create import (
    create_test_invocation_runs,
)

ARTIFACT = "test"
OPERATION = "run"


class TestRunInternalResult(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_invocation_run_id: str
    success: bool = True
    idempotency_key: UUID | None = None


async def test_run_internal_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn | None = None,
    audit: bool = True,
) -> TestRunInternalResult:
    """Insert a test_invocation_runs_entry binding row."""
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

    soft = bool(data.get("soft", False))
    accept = data.get("accept")
    idempotency_key = data.get("idempotency_key")
    if isinstance(idempotency_key, str):
        idempotency_key = UUID(idempotency_key)
    is_ack = accept is not None and idempotency_key is not None

    async def _run(call_id: UUID | None = None) -> TestRunInternalResult:
        redis = get_redis_client()

        # ── Short-circuit: ack — activate / reject the staged binding ──
        if accept is not None and idempotency_key is not None:
            async with get_pool().acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != OPERATION:
                raise HTTPException(status_code=404, detail="No pending run binding for this call.")
            ids = entry.patch or {}
            run_row_id = ids.get("test_invocation_run_id")
            if accept and run_row_id:
                async with get_pool().acquire() as conn:
                    await activate_rows(conn, table="test_invocation_runs_entry", ids=[UUID(run_row_id)])
                await refresh_invocation_impl(
                    get_pool(), redis,
                    profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
                    targets=["test_invocation_runs_mv"],
                )
            async with get_pool().acquire() as conn:
                async with conn.transaction():
                    # A2: on REJECT, hard-delete the dormant (active=False) binding
                    # row in the SAME txn as the terminal ledger write. The dormant
                    # row is MV-invisible, so leaving it behind both leaks a row
                    # forever AND lets a later stray activate_rows/replay resurrect
                    # a rejected binding into the live MV. Deleting it closes both.
                    if not accept and run_row_id:
                        await delete_artifacts(
                            conn, table="test_invocation_runs_entry",
                            ids=[UUID(run_row_id)],
                        )
                    await create_soft_call(
                        conn, redis, call_id=idempotency_key, artifact=ARTIFACT,
                        operation=OPERATION, artifact_id=entry.artifact_id,
                        status="accepted" if accept else "rejected",
                    )
            # A1: a reject ack is NOT a successful commit — return
            # ``success=False`` so the wrapper's ``.completed`` payload can't
            # be mistaken for an accepted binding. The ack threads
            # ``idempotency_key`` as the wrapper ``call_id`` (see audit call
            # below), so the ``.completed`` ledger lookup resolves
            # ``ledger_status`` to "rejected" (not null) for live watchers.
            return TestRunInternalResult(
                test_invocation_run_id=str(run_row_id or ""),
                success=bool(accept),
                idempotency_key=idempotency_key,
            )

        # ── Owner/role/department scope (BOLA + cross-dept guard, T4) ──────
        # The binding-row insert below is keyed solely by the caller-supplied
        # ``test_invocation_id``. Without this, any authenticated profile could
        # bind a run into ANOTHER user's invocation, polluting its run/trace
        # chain (which feeds its later grade/aggregate). Resolve invocation →
        # owner and route through the shared attempt-mutation gate.
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

        with timed("db_write"):
            async with get_pool().acquire() as conn:
                async with conn.transaction():
                    result = await create_test_invocation_runs(
                        conn, redis,
                        test_invocation_id=payload.test_invocation_id,
                        run_id=payload.run_id,
                        test_invocation_traces_id=payload.test_invocation_trace_id,
                        soft=soft,
                    )
                    if soft and call_id is not None:
                        await create_soft_call(
                            conn, redis, call_id=call_id, artifact=ARTIFACT,
                            operation=OPERATION, artifact_id=result.id, status="pending",
                            patch={"test_invocation_run_id": str(result.id)},
                        )
        if not soft:
            with timed("refresh"):
                await refresh_invocation_impl(
                    get_pool(), redis,
                    profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)),
                    targets=["test_invocation_runs_mv"],
                )
        return TestRunInternalResult(
            test_invocation_run_id=str(result.id),
            idempotency_key=call_id,
        )

    if not audit:
        return await _run()

    # Resolve the time-windowed test group — the wrapper only mints a calls_entry
    # (which the soft ledger + call_id threading need) when group_id is present.
    from app.infra.test.group import group_test_impl
    group_result = await group_test_impl(
        get_pool(), get_redis_client(),
        profile_id=UUID(str(profile_id)), session_id=UUID(str(session_id)), id_only=True,
    )

    return await run_artifact_operation_with_audit(
        get_pool(),
        get_redis_client(),
        artifact=ARTIFACT,
        profile_id=UUID(str(profile_id)),
        group_id=group_result.group_id,
        operation=OPERATION,
        runner=_run,
        arguments={"accept": accept} if is_ack else build_audit_arguments(data),
        operation_key=idempotency_key,  # idempotency replay gate
        # A1: for an ack, thread the ack's idempotency_key as the wrapper
        # call_id so emit_call_id == the soft-ledger key the ack writes —
        # the .completed ledger lookup then resolves ledger_status to
        # "accepted"/"rejected" instead of null.
        call_id=idempotency_key if is_ack else None,
        session_id=UUID(str(session_id)),
        entity_id=payload.test_invocation_id,
        test_id=payload.test_id,
        response_model=TestRunInternalResult,
    )
