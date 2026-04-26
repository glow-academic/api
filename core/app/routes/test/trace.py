"""Test trace endpoint — open a trace on a test invocation.

POST /test/trace — creates the conversation/bundle context for a turn
of test execution. Client then calls /test/generate with the returned
trace_id (analogous to attempt's chat→message→generate sequence).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.test.trace import (
    TestTraceInternalResult,
    TestTracePayload,
    test_trace_internal_impl,
)

router = APIRouter()


@router.post("/trace", response_model=TestTraceInternalResult)
async def test_trace(
    request: TestTracePayload,
    http_request: Request,
) -> TestTraceInternalResult:
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await test_trace_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
