"""Test run end endpoint — POST /test/run/end.

Writes test_invocation_runs_completion_entry, marking the binding row
as finished. Mirrors /attempt/chat/silence (the voice end-of-turn).
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
from app.tools.entries.test_invocation_runs_completion.refresh import (
    refresh_test_invocation_runs_completion,
)

router = APIRouter()


class TestRunEndPayload(BaseModel):
    test_invocation_run_id: UUID = Field(
        ..., description="UUID of the test_invocation_runs_entry to finalize"
    )
    success: bool = True
    error: bool = False
    message: str = ""


class TestRunEndResponse(BaseModel):
    test_invocation_run_id: str
    completion_id: str
    success: bool = True


@router.post("/end", response_model=TestRunEndResponse)
async def run_test_end(
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
        async with pool.acquire() as conn:
            runs = await get_test_invocation_runs(
                conn, [request.test_invocation_run_id]
            )
            if not runs:
                raise HTTPException(
                    status_code=404,
                    detail=f"test_invocation_run {request.test_invocation_run_id} not found",
                )
            run = runs[0]
            invs = await get_test_invocations(
                conn, [run.test_invocation_id], bypass_mv=True,
            )
            if not invs:
                raise HTTPException(status_code=404, detail="parent invocation not found")
            inv = invs[0]
            group_id = inv.group_id
            if group_id is None:
                raise HTTPException(status_code=400, detail="invocation has no group_id")
            groups = await get_groups(conn, [group_id])
            if not groups or groups[0].session_id is None:
                raise HTTPException(status_code=400, detail="group has no session_id")
            new_run = await create_run(
                conn, group_id=group_id, session_id=groups[0].session_id,
            )
            call = await create_call(
                conn, run_id=new_run.id, session_id=groups[0].session_id,
            )
            completion = await create_test_invocation_runs_completion(
                conn,
                test_invocation_runs_id=request.test_invocation_run_id,
                call_id=call.id,
                stop=False,
                error=request.error,
                message=request.message,
            )
            await refresh_test_invocation_runs_completion(conn)

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
            operation="run_end",
            runner=_runner,
            arguments=build_audit_arguments(request.model_dump(mode="json")),
            response_model=TestRunEndResponse,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
