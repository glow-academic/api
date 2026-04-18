"""System generate logic — deterministic infra architecture.

Calls prepare_generation -> execute_generation directly.
No generic websocket events. Tool calls emit through audit path.
Text streaming emits system.generate.progress.

The `dangerous` flag controls tool call behavior inside the generation:
  - dangerous=False (default): tool calls use soft=True (dormant, pending acceptance)
  - dangerous=True: tool calls execute fully (immediate)

Generation itself always runs -- prepare + execute.

Flow:
  1. resolve_profile_identity_context -> role, permissions
  2. Permission check -- system:generate
  3. Validate resources against registry
  4. prepare_generation -- create run, resolve context, build dispatches
  5. execute_generation -- agentic LLM loop (tool calls soft based on dangerous)
  6. System has no dedicated refresh — child artifacts handle their own
"""

from __future__ import annotations

import uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.generation.execute import execute_generation
from app.infra.generation.prepare import prepare_generation
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
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

ARTIFACT_TYPE = "system"


async def generate_system_impl(
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
    """System generation using deterministic infra functions.

    Generation always runs (prepare + execute). The `dangerous` flag
    on the request controls whether tool calls inside the generation
    use soft=True (dormant, pending acceptance) or soft=False (immediate).
    """
    internal_sio = get_internal_sio()
    resolved_sid = sid or f"http-{uuid.uuid4()}"
    cfg = request.config or GenerateConfig()

    # dangerous=False -> tool calls are soft (pending). dangerous=True -> immediate.
    tool_soft = not cfg.dangerous

    # -- Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # -- Step 1: Profile context -----------------------------------------------

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check ----------------------------------------------

    if not has_permission(profile.role_permissions, ARTIFACT_TYPE, "generate"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to generate system operations.",
        )

    # -- Step 3: Validate resources --------------------------------------------

    group_id = cfg.group_id
    if not group_id:
        # Resolve group from Redis time window (same as persona)
        from app.tools.entries.groups.create import create_group
        async with pool.acquire() as conn:
            group_result = await create_group(conn, session_id=session_id, artifact_type=ARTIFACT_TYPE)
            group_id = group_result.id

    config = REGISTRY.get(ARTIFACT_TYPE)
    if not config:
        raise HTTPException(status_code=400, detail=f"No config for {ARTIFACT_TYPE}")

    # -- Step 4: Prepare + Execute ---------------------------------------------

    generated_key = idempotency_key or uuid.uuid4()
    payload = GeneratePayload(
        artifact_type=ARTIFACT_TYPE,
        instructions=request.instructions,
        operations=cfg.operations,
        dangerous=cfg.dangerous,
        params=cfg.params,
    )

    try:
        prepared = await prepare_generation(
            pool, redis,
            profile_id=profile_id,
            profiles_id=profile.profiles_id,
            session_id=session_id,
            group_id=uuid.UUID(str(group_id)),
            artifact_type=ARTIFACT_TYPE,
            artifact_config=config,
            payload=payload,
        )

        logger.info(
            f"GENERATE_SYSTEM: prepared run_id={prepared.run_id}, "
            f"dispatches={len(prepared.dispatches)}, "
            f"resource_types={prepared.resource_types}"
        )

        # Emit text.complete for each persisted message (system, developer, user)
        for dispatch in prepared.dispatches:
            for msg in dispatch.messages:
                role = msg.get("role", "")
                content = msg.get("content", "")
                if role and content:
                    await internal_sio.emit(
                        f"{ARTIFACT_TYPE}.generate.text.complete",
                        {
                            "sid": resolved_sid,
                            "rooms": [resolved_sid] if resolved_sid else [],
                            "artifact_type": ARTIFACT_TYPE,
                            "run_id": str(prepared.run_id),
                            "group_id": str(group_id),
                            "role": role,
                            "text": content,
                        },
                    )

        result = await execute_generation(
            pool, redis,
            prepared=prepared,
            sid=resolved_sid,
            tool_soft=tool_soft,
        )

        # System has no dedicated refresh — child artifacts handle their own

    except Exception as e:
        logger.exception(f"System generation failed: {e}")
        raise

    return ArtifactGenerateResponse(
        group_id=str(group_id),
        idempotency_key=str(generated_key),
    )
