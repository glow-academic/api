"""Test run endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.test.client_types import TestRunPayload
from app.infra.test.run import test_run_internal_impl

router = APIRouter()


class RunTestApiResponse(BaseModel):
    test_id: str
    invocation_id: str
    run_id: str


@router.post("/run", response_model=RunTestApiResponse)
async def run_test(
    request: TestRunPayload,
    http_request: Request,
) -> RunTestApiResponse:
    """Run one auto-regressive replay. Returns immediately; progress via socket."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await test_run_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return RunTestApiResponse.model_validate(result.model_dump(mode="json"))
