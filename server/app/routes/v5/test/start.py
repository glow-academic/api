"""Test start endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.test.client_types import TestStartPayload
from app.infra.test.start import test_start_internal_impl

router = APIRouter()


class StartTestApiResponse(BaseModel):
    test_id: str


@router.post("/start", response_model=StartTestApiResponse)
async def start_test(
    request: TestStartPayload,
    http_request: Request,
) -> StartTestApiResponse:
    """Create a new test."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await test_start_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StartTestApiResponse(test_id=result.test_id)
