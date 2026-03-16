"""Attempt join endpoint — POST /v5/attempt/join.

Adds a chat entity to the caller's stream session after verifying
the caller has access to the underlying attempt.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.attempt.permissions import check_attempt_access
from app.infra.globals import get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.stream.session import get_session_profile, join_entity

router = APIRouter()


class AttemptJoinRequest(BaseModel):
    sid: str
    chat_id: UUID


class AttemptJoinResponse(BaseModel):
    success: bool


@router.post("/join", response_model=AttemptJoinResponse)
async def attempt_join(
    request: AttemptJoinRequest,
    http_request: Request,
) -> AttemptJoinResponse:
    """Join a chat room for real-time attempt updates."""
    profile_id: UUID | None = getattr(http_request.state, "profile_id", None)
    if not profile_id:
        raise HTTPException(status_code=401, detail="Profile ID is required.")

    profile_id = UUID(str(profile_id))

    # Validate session ownership
    session_profile = await get_session_profile(request.sid)
    if not session_profile or session_profile != profile_id:
        raise HTTPException(status_code=403, detail="Session not found or not owned.")

    pool = get_pool()
    redis = get_redis_client()

    # Look up the chat to find the attempt owner
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT profile_id FROM attempt_chat_mv WHERE chat_id = $1",
            request.chat_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail="Chat not found.")

    chat_profile_id: UUID | None = row["profile_id"]

    # Resolve the requester's role
    session_id: UUID | None = getattr(http_request.state, "session_id", None)
    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id
    )
    if not identity:
        raise HTTPException(status_code=401, detail="Could not resolve profile.")

    # Check access using existing attempt permission logic
    if not check_attempt_access(
        attempt_profile_id=chat_profile_id,
        request_profile_id=identity.profiles_id,
        request_role=identity.role,
    ):
        raise HTTPException(status_code=403, detail="Access denied.")

    await join_entity(request.sid, "attempt", request.chat_id)
    return AttemptJoinResponse(success=True)
