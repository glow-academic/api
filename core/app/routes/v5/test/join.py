"""Test join endpoint — POST /v5/test/join.

Adds a test invocation entity to the caller's stream session.
Tests currently require only an authenticated profile (no role-based
access hierarchy like attempts).  The permission logic lives here so it
can be tightened later without touching central infrastructure.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_pool
from app.infra.stream.session import get_session_profile, join_entity

router = APIRouter()


class TestJoinRequest(BaseModel):
    sid: str
    invocation_id: UUID


class TestJoinResponse(BaseModel):
    success: bool


@router.post("/join", response_model=TestJoinResponse)
async def test_join(
    request: TestJoinRequest,
    http_request: Request,
) -> TestJoinResponse:
    """Join a test invocation room for real-time updates."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    profile_id = UUID(str(profile_id))

    session_profile = await get_session_profile(request.sid)
    if not session_profile or session_profile != profile_id:
        raise HTTPException(status_code=403, detail="Session not found or not owned.")

    # Verify the invocation exists
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT test_invocation_id FROM test_invocation_entry WHERE test_invocation_id = $1",
            request.invocation_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Test invocation not found.")

    await join_entity(request.sid, "test", request.invocation_id)
    return TestJoinResponse(success=True)
