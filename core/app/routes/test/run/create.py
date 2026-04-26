"""Test run create endpoint — POST /test/run.

Pure binding-row writer. Mirrors /attempt/chat/message — primitive,
no orchestration. Caller passes { test_id, test_invocation_id, run_id,
test_invocation_trace_id? } to bind a runs_entry to a test invocation.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.test.client_types import TestRunPayload
from app.infra.test.run import (
    TestRunInternalResult,
    test_run_internal_impl,
)

router = APIRouter()


@router.post("/", response_model=TestRunInternalResult)
async def run_test(
    request: TestRunPayload,
    http_request: Request,
) -> TestRunInternalResult:
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await test_run_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
