"""Test next endpoint — thin HTTP adapter over internal orchestration."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.test.client_types import TestNextPayload
from app.infra.test.next import test_next_internal_impl

router = APIRouter()


class NextTestApiResponse(BaseModel):
    invocation_id: str
    run_id: str
    current_run: int
    total_runs: int


@router.post("/next", response_model=NextTestApiResponse)
async def next_test(
    request: TestNextPayload,
    http_request: Request,
) -> NextTestApiResponse:
    """Find next pending run in an existing test."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)
    if not profile_id or not session_id:
        raise HTTPException(status_code=401, detail="Missing profile or session")

    try:
        result = await test_next_internal_impl(
            {
                "profile_id": str(profile_id),
                "session_id": str(session_id),
                **request.model_dump(mode="json"),
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return NextTestApiResponse.model_validate(result.model_dump(mode="json"))
