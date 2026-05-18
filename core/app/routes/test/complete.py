"""Test complete endpoint — thin HTTP adapter for the canonical
whole-test completion. Mirrors POST /attempt/complete."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.infra.test.client_types import TestCompletePayload
from app.infra.test.complete import (
    TestCompleteInternalResult,
    test_complete_internal_impl,
)

router = APIRouter()


@router.post("/complete", response_model=TestCompleteInternalResult)
async def complete_test(
    request: TestCompletePayload,
    http_request: Request,
) -> TestCompleteInternalResult:
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        return await test_complete_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
