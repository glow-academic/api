"""Test invocation terminate endpoint — POST /test/invocation/terminate.

Writes test_invocation_runs_completion_entry, marking the run binding row
as finished. Renamed from /test/run/end and relocated under invocation/.
Mirrors /attempt/chat/silence (the voice end-of-turn). "Terminate" matches
the actual semantics — the row is finalized, no resume path. If
pause/resume semantics become a requirement later, that's a separate
endpoint with a `resumable` flag on the completion row.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.infra.events.audit import (
    build_audit_arguments,
    run_artifact_operation_with_audit,
)
from app.infra.globals import get_pool, get_redis_client
from app.tools.entries.calls.create import create_call
from app.tools.entries.groups.get import get_groups
from app.tools.entries.runs.create import create_run
from app.tools.entries.test_invocation.get import get_test_invocations
from app.tools.entries.test_invocation_runs.get import get_test_invocation_runs
from app.tools.entries.test_invocation_runs_completion.create import (
    create_test_invocation_runs_completion,
)
from app.infra.invocation.refresh import refresh_invocation_impl

router = APIRouter()


class TestRunEndPayload(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_invocation_run_id: UUID = Field(
        ..., description="UUID of the test_invocation_runs_entry to finalize"
    )
    success: bool = True
    error: bool = False
    message: str = ""
    idempotency_key: UUID | None = Field(None, description="Idempotency key — replays the prior call instead of re-running")


class TestRunEndResponse(BaseModel):
    __test__ = False  # pytest: not a test class (domain model)
    test_invocation_run_id: str
    completion_id: str
    success: bool = True


@router.post("/invocation_terminate", response_model=TestRunEndResponse)
async def terminate_invocation(
    request: TestRunEndPayload,
    http_request: Request,
) -> TestRunEndResponse:
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    pool = get_pool()
    redis = get_redis_client()

    async def _runner() -> TestRunEndResponse:
        # ── Owner/role/department scope (BOLA + cross-dept guard, T3) ──────
        # The runs-completion insert below is keyed solely by the caller-
        # supplied ``test_invocation_run_id``. Without this, any authenticated
        # profile could finalize/terminate ANOTHER user's benchmark run (the
        # run-keyed analogue of the ``stop_attempt`` M1 IDOR). Resolve
        # run → invocation → owner and route through the shared gate.
        from app.infra.profile_identity_context import (
            resolve_profile_identity_context,
        )
        from app.infra.test.permissions import enforce_test_access_by_run

        requester = await resolve_profile_identity_context(
            pool, UUID(str(profile_id)), redis,
        )
        await enforce_test_access_by_run(
            pool, redis,
            run_id=request.test_invocation_run_id, requester=requester,
        )

        async with pool.acquire() as conn:
            runs = await get_test_invocation_runs(
                conn, [request.test_invocation_run_id], redis
            )
            if not runs:
                raise HTTPException(
                    status_code=404,
                    detail=f"test_invocation_run {request.test_invocation_run_id} not found",
                )
            run = runs[0]
            invs = await get_test_invocations(
                conn, [run.test_invocation_id], redis,
            )
            if not invs:
                raise HTTPException(status_code=404, detail="parent invocation not found")
            inv = invs[0]
            group_id = inv.group_id
            if group_id is None:
                raise HTTPException(status_code=400, detail="invocation has no group_id")
            groups = await get_groups(conn, [group_id], redis)
            if not groups or groups[0].session_id is None:
                raise HTTPException(status_code=400, detail="group has no session_id")
            new_run = await create_run(
                conn, redis, group_id=group_id, session_id=groups[0].session_id,
            )
            call = await create_call(
                conn, redis, run_id=new_run.id, session_id=groups[0].session_id,
            )
            completion = await create_test_invocation_runs_completion(
                conn, redis,
                test_invocation_runs_id=request.test_invocation_run_id,
                call_id=call.id,
                stop=False,
                error=request.error,
                message=request.message,
            )
        await refresh_invocation_impl(
            pool, redis,
            profile_id=UUID(str(profile_id)),
            session_id=UUID(str(session_id)),
            targets=["test_invocation_runs_completion_mv"],
        )

        return TestRunEndResponse(
            test_invocation_run_id=str(request.test_invocation_run_id),
            completion_id=str(completion.id),
            success=request.success,
        )

    try:
        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="test",
            profile_id=UUID(str(profile_id)),
            session_id=UUID(str(session_id)),
            operation="invocation_terminate",
            runner=_runner,
            arguments=build_audit_arguments(request.model_dump(mode="json")),
            response_model=TestRunEndResponse,
            operation_key=request.idempotency_key,  # idempotency replay gate
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
