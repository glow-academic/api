"""Persona generate logic — per-artifact generation entry point.

Fire-and-return: resolves identity, checks persona:generate permission,
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
)
from app.registry.generate import REGISTRY

ARTIFACT_TYPE = "persona"


async def generate_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: ArtifactGenerateRequest,
    sid: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> ArtifactGenerateResponse:
    """Trigger persona generation.

    Lifecycle via soft + accept:
      - soft=True: validate only, return idempotency_key. LLM doesn't run.
      - accept=True: emit to bus, full generation pipeline starts.
      - accept=False: no-op.

    Flow:
      1. resolve_profile_identity_context → role, permissions
      2. Permission check — persona:generate
      3. Validate resources against registry
      4. Emit to internal bus (skipped when soft)
      5. Return group_id + idempotency_key
    """
    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or (
        uuid.UUID(request.idempotency_key) if request.idempotency_key else None
    )
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        group_id = request.group_id
        if accept:
            # Accept: now emit to the bus — full pipeline runs
            profile = await resolve_profile_identity_context(
                pool, profile_id, redis, session_id=session_id,
            )
            if profile is None:
                raise HTTPException(status_code=401, detail="Profile not found.")

            payload = request.to_generate_payload(ARTIFACT_TYPE)
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
        # accept=False: no-op (generation never starts)
        return ArtifactGenerateResponse(
            group_id=str(group_id) if group_id else "",
            idempotency_key=str(idempotency_key),
        )

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
            detail="You don't have permission to generate personas.",
        )

    # ── Step 3: Validate resources ─────────────────────────────────────

    group_id = request.group_id
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id is required")

    config = REGISTRY.get(ARTIFACT_TYPE)
    if config and request.resources:
        invalid = set(request.resources) - set(config.valid_resource_types)
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid resources for {ARTIFACT_TYPE}: {sorted(invalid)}",
            )

    # ── Step 4: Soft — validate only, don't emit ─────────────────────

    generated_key = idempotency_key or uuid.uuid4()

    if soft:
        return ArtifactGenerateResponse(
            group_id=str(group_id),
            idempotency_key=str(generated_key),
        )

    # ── Step 5: Emit to internal bus ──────────────────────────────────

    payload = request.to_generate_payload(ARTIFACT_TYPE)

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

    return ArtifactGenerateResponse(
        group_id=str(group_id),
        idempotency_key=str(generated_key),
    )
