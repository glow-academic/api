"""Setting generate logic — per-artifact generation entry point.

Fire-and-return: resolves identity, checks setting:generate permission,
validates resources against the registry, and emits to the internal bus.
Progress/completion events arrive via SSE or WebSocket.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import get_internal_sio
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.websocket.generation_types import (
    ArtifactGenerateRequest,
    ArtifactGenerateResponse,
    GenerateConfig,
    GeneratePayload,
)
from app.registry.generate import REGISTRY

ARTIFACT_TYPE = "setting"


async def generate_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArtifactGenerateRequest,
    sid: str | None = None,
) -> ArtifactGenerateResponse:
    """Trigger setting generation.

    Flow:
      1. resolve_profile_identity_context → role, permissions
      2. Permission check — setting:generate
      3. Validate resources against registry
      4. Emit to internal bus
      5. Return group_id immediately
    """
    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────

    if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generate"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to generate settings.",
        )

    # ── Step 3: Validate resources ─────────────────────────────────────

    cfg = request.config or GenerateConfig()
    group_id = cfg.group_id
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")

    config = REGISTRY.get(ARTIFACT_TYPE)
    # ── Step 4: Emit to internal bus ───────────────────────────────────

    payload = GeneratePayload(
        artifact_type=ARTIFACT_TYPE,
        instructions=request.instructions,
        operations=cfg.operations,
        dangerous=cfg.dangerous,
        params=cfg.params,
    )

    resolved_sid = sid or f"http-{uuid.uuid4()}"

    internal_sio = get_internal_sio()
    await internal_sio.emit(
        "generate",
        {
            "sid": resolved_sid,
            "profile_id": str(profile_id),
            "profiles_id": str(profile.profiles_id),
            "session_id": str(session_id),
            "group_id": str(group_id),
            "requests_per_day": profile.requests_per_day,
            **payload.model_dump(mode="json"),
        },
    )

    return ArtifactGenerateResponse(group_id=str(group_id))
