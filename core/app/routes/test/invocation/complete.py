"""Test invocation complete endpoint — thin HTTP adapter for the
canonical per-invocation completion. Mirrors POST /attempt/chat/complete."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.test.client_types import TestInvocationCompletePayload
from app.infra.test.invocation.complete import (
    TestInvocationCompleteInternalResult,
    test_invocation_complete_internal_impl,
)

router = APIRouter()


@router.post("/complete", response_model=TestInvocationCompleteInternalResult)
async def complete_invocation(
    request: TestInvocationCompletePayload,
    http_request: Request,
) -> TestInvocationCompleteInternalResult:
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await test_invocation_complete_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
