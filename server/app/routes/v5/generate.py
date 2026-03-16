"""Group generate endpoint — HTTP adapter for the canonical generate pipeline.

Fire-and-return equivalent of the ``generate`` WebSocket event.
Resolves identity context, emits to the internal ``generate`` event, and
returns ``group_id`` immediately. Progress/completion events arrive via
SSE at ``/v5/stream``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.infra.globals import get_internal_sio, get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.generation_types import GeneratePayload

router = APIRouter()


class GenerateApiResponse(BaseModel):
    group_id: str


@router.post("/generate", response_model=GenerateApiResponse)
async def generate(
    request: GeneratePayload,
    http_request: Request,
) -> GenerateApiResponse:
    """Trigger artifact generation. Returns immediately; progress via events."""
    profile_id = getattr(http_request.state, "profile_id", None)
    session_id = getattr(http_request.state, "session_id", None)

    if not profile_id:
        raise HTTPException(
            status_code=401,
            detail="Profile ID is required. Please sign in again.",
        )
    if not session_id:
        raise HTTPException(
            status_code=401,
            detail="Session ID is required. Please sign in again.",
        )

    group_id = request.group_id
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")

    # Resolve ProfileContext — same as client socket handler
    pool = get_pool()
    redis = get_redis_client()
    profile_ctx = await resolve_profile_identity_context(
        pool,
        uuid.UUID(str(profile_id)),
        redis,
        session_id=uuid.UUID(str(session_id)),
    )

    if not profile_ctx:
        raise HTTPException(
            status_code=401,
            detail="Profile context not found. Please sign in again.",
        )

    # Synthetic sid — the generation pipeline routes socket events via sid.
    # HTTP clients receive progress/completion through SSE instead.
    synthetic_sid = f"http-{uuid.uuid4()}"

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "generate",
        {
            "sid": synthetic_sid,
            "profile_id": str(profile_id),
            "profiles_id": str(profile_ctx.profiles_id),
            "session_id": str(session_id),
            "group_id": str(group_id),
            "requests_per_day": profile_ctx.requests_per_day,
            **request.model_dump(mode="json"),
        },
    )

    return GenerateApiResponse(group_id=str(group_id))
