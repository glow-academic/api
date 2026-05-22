"""Field generate logic — deterministic infra architecture.

Calls prepare_generation -> execute_generation directly.
No generic websocket events. Tool calls emit through audit path.
Text streaming emits field.generate.progress.

The `dangerous` flag controls tool call behavior inside the generation:
  - dangerous=False (default): tool calls use soft=True (dormant, pending acceptance)
  - dangerous=True: tool calls execute fully (immediate)

Generation itself always runs - prepare + execute.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.field.refresh import refresh_field_impl
from app.infra.generation.execute import execute_generation
from app.infra.generation.runner import run_generation_with_refresh
from app.infra.generation.prepare import prepare_generation
from app.infra.globals import get_internal_sio
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.websocket.generation_types import (
    ArtifactGenerateResponse,
    GeneratePayload,
)
from app.registry.generate import REGISTRY

ARTIFACT_TYPE = "field"


async def generate_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    instructions: list[str] | None = None,
    modalities: list[str] | None = None,
    audios_id: UUID | None = None,
    conversation_id: UUID | None = None,
    trace_id: UUID | None = None,
    operations: list[str] | None = None,
    dangerous: bool = False,
    params: dict | None = None,
    group_id: UUID | str | None = None,
    wait_for_complete: bool | None = None,
    instructions_role: str = "user",
    sid: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **_kwargs,
) -> ArtifactGenerateResponse:
    """Field generation using deterministic infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. Permission check -- field:generate
      3. Validate resources against registry
      4. Prepare + Execute
      5. Canonical refresh
    """
    internal_sio = get_internal_sio()
    if sid:
        resolved_sid = sid
    else:
        from app.infra.websocket.get_socket_owner import get_socket_owner
        resolved_sid = await get_socket_owner(str(profile_id)) or ""

    # dangerous=False -> tool calls are soft (pending). dangerous=True -> immediate.
    tool_soft = not dangerous

    # Merge ack fields from request (HTTP) or params (generation pipeline).

    # -- Step 1: Profile context ----------------------------------------

    with timed("profile"):
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

    # -- Step 2: Permission check ---------------------------------------

    with timed("permissions"):
        if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generate"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to generate fields.",
            )

    # -- Step 3: Validate resources -------------------------------------
    from app.infra.group.resolve import resolve_group_impl
    # Always resolve — resolve_group_impl idempotently upserts when a
    # client-minted group_id is supplied, or falls back to window-based
    # auto-create when omitted. Either way the groups_entry row exists
    # before any FK-referencing run/message insert downstream.
    with timed("group"):
        group_result = await resolve_group_impl(
            pool, redis,
            artifact_type=ARTIFACT_TYPE,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            include_history=False,
        )
    group_id = group_result.group_id
    config = REGISTRY.get(ARTIFACT_TYPE)
    if not config:
        raise HTTPException(status_code=400, detail=f"No config for {ARTIFACT_TYPE}")

    # -- Step 4: Prepare + Execute --------------------------------------

    payload = GeneratePayload(
        artifact_type=ARTIFACT_TYPE,
        instructions=instructions,
        instructions_role=instructions_role,
        operations=operations,
        dangerous=dangerous,
        modalities=modalities,
        params=params,
    )

    generated_key = idempotency_key or uuid.uuid4()
    with timed("prepare"):
        prepared = await prepare_generation(
            pool,
            redis,
            profile_id=profile_id,
            profiles_id=profile.profiles_id,
            session_id=session_id,
            group_id=uuid.UUID(str(group_id)),
            artifact_type=ARTIFACT_TYPE,
            artifact_config=config,
            payload=payload,
            soft=soft,
        )

    for dispatch in prepared.dispatches:
        for msg in dispatch.messages:
            # Skip history items threaded by prepare.py — already
            # shown via group_get; re-emitting yields duplicates.
            if not msg.get("_emit", True):
                continue
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role and content:
                await internal_sio.emit(
                    f"{ARTIFACT_TYPE}.generate.text.complete",
                    {
                        "sid": resolved_sid,
                        "rooms": [str(profile_id)],
                        "artifact_type": ARTIFACT_TYPE,
                        "run_id": str(prepared.run_id),
                        "group_id": str(group_id),
                        "role": role,
                        "text": content,
                    },
                )

    # ── Run (blocking by default; opt-in fire-and-forget via
    # ``wait_for_complete=False`` — pair with X_Watch).
    wait_for_complete = wait_for_complete
    if wait_for_complete is None:
        wait_for_complete = True

    with timed("execute"):
        run_result = await run_generation_with_refresh(
            pool, redis,
            prepared=prepared,
            sid=resolved_sid,
            tool_soft=tool_soft,
            artifact_type=ARTIFACT_TYPE,
            refresh_fn=refresh_field_impl,
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            internal_sio=internal_sio,
            wait_for_complete=wait_for_complete,
            operation_key=generated_key,
        )

    return ArtifactGenerateResponse(
        group_id=str(group_id),
        run_id=str(prepared.run_id),
        idempotency_key=generated_key,
        produced_media=run_result.produced_media if run_result else [],
    )
