"""Test stop endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.test.client_types import TestStopPayload
from app.infra.test.stop import test_stop_internal_impl

router = APIRouter()


class StopTestApiResponse(BaseModel):
    invocation_id: str
    success: bool
    message: str | None = None


@router.post("/stop", response_model=StopTestApiResponse)
async def stop_test(
    request: TestStopPayload,
    http_request: Request,
) -> StopTestApiResponse:
    """Stop current test execution."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await test_stop_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StopTestApiResponse.model_validate(result.model_dump(mode="json"))
