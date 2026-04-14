"""Persona generate logic — deterministic infra architecture.

Calls prepare_generation → execute_generation directly.
No generic websocket events. Tool calls emit through audit path.
Text streaming emits persona.generate.progress.

Flow:
  1. resolve_profile_identity_context → role, permissions
  2. Permission check — persona:generate
  3. Validate resources against registry
  4. prepare_generation — create run, resolve context, build dispatches
  5. execute_generation — agentic LLM loop
  6. Emit persona.generate.completed
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
    GeneratePayload,
)
from app.registry.generate import REGISTRY
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

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
    """Persona generation using deterministic infra functions.

    Lifecycle via soft + accept:
      - soft=True: prepare only (run with active=false, context resolved,
        messages persisted). LLM doesn't run, no cost.
      - accept=True: prepare + execute (full generation).
      - accept=False: no-op.
      - neither (normal): prepare + execute immediately.
    """
    internal_sio = get_internal_sio()
    resolved_sid = sid or f"http-{uuid.uuid4()}"

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

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
    if not config:
        raise HTTPException(status_code=400, detail=f"No config for {ARTIFACT_TYPE}")

    if request.resources:
        invalid = set(request.resources) - set(config.valid_resource_types)
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid resources for {ARTIFACT_TYPE}: {sorted(invalid)}",
            )

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            # Accept: prepare + execute
            payload = request.to_generate_payload(ARTIFACT_TYPE)

            await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.started", {
                "sid": resolved_sid,
                "rooms": [resolved_sid] if resolved_sid else [],
                "artifact_type": ARTIFACT_TYPE,
                "group_id": str(group_id),
            })

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

                result = await execute_generation(
                    pool, redis,
                    prepared=prepared,
                    sid=resolved_sid,
                )

                await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.completed", {
                    "sid": resolved_sid,
                    "rooms": [resolved_sid] if resolved_sid else [],
                    "artifact_type": ARTIFACT_TYPE,
                    "group_id": str(group_id),
                    "run_id": str(prepared.run_id),
                    "success": True,
                    "input_tokens": result.total_input_tokens,
                    "output_tokens": result.total_output_tokens,
                })
            except Exception as e:
                logger.exception(f"Persona generation failed: {e}")
                await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.failed", {
                    "sid": resolved_sid,
                    "rooms": [resolved_sid] if resolved_sid else [],
                    "artifact_type": ARTIFACT_TYPE,
                    "group_id": str(group_id),
                    "message": str(e),
                })

        # accept=False: no-op
        return ArtifactGenerateResponse(
            group_id=str(group_id),
            idempotency_key=str(idempotency_key),
        )

    # ── Step 4: Build payload ─────────────────────────────────────────

    generated_key = idempotency_key or uuid.uuid4()
    payload = request.to_generate_payload(ARTIFACT_TYPE)

    # ── Step 5: Soft — prepare only, don't execute ────────────────────

    if soft:
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
                soft=True,
            )
            return ArtifactGenerateResponse(
                group_id=str(group_id),
                idempotency_key=str(prepared.run_id),
            )
        except Exception as e:
            logger.exception(f"Persona generation prepare failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    # ── Step 6: Normal — prepare + execute immediately ────────────────

    await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.started", {
        "sid": resolved_sid,
        "rooms": [resolved_sid] if resolved_sid else [],
        "artifact_type": ARTIFACT_TYPE,
        "group_id": str(group_id),
    })

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

        result = await execute_generation(
            pool, redis,
            prepared=prepared,
            sid=resolved_sid,
        )

        await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.completed", {
            "sid": resolved_sid,
            "rooms": [resolved_sid] if resolved_sid else [],
            "artifact_type": ARTIFACT_TYPE,
            "group_id": str(group_id),
            "run_id": str(prepared.run_id),
            "success": True,
            "input_tokens": result.total_input_tokens,
            "output_tokens": result.total_output_tokens,
        })
    except Exception as e:
        logger.exception(f"Persona generation failed: {e}")
        await internal_sio.emit(f"{ARTIFACT_TYPE}.generate.failed", {
            "sid": resolved_sid,
            "rooms": [resolved_sid] if resolved_sid else [],
            "artifact_type": ARTIFACT_TYPE,
            "group_id": str(group_id),
            "message": str(e),
        })

    return ArtifactGenerateResponse(
        group_id=str(group_id),
        idempotency_key=str(generated_key),
    )
