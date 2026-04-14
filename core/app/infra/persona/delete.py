"""Persona delete logic — composable infra architecture.

Core delete function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. resolve_persona_permissions_context — per-item exists, departments, usage
  3. compute_can_delete — permission check
  4. delete_personas — bulk delete tool
  5. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.persona.permissions import compute_can_delete
from app.infra.persona.permissions_context import resolve_persona_permissions_context
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    DeletePersonaApiResponse,
    DeletePersonaResult,
)
from app.infra.delete.delete_artifact import restore_artifacts
from app.infra.persona.refresh import refresh_persona_impl
from app.tools.artifacts.persona.delete import delete_personas
from app.tools.artifacts.persona.get import get_personas
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def delete_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    persona_ids: list[UUID],
    session_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> DeletePersonaApiResponse:
    """Persona bulk delete using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. Per-item: resolve_persona_permissions_context → exists, departments, usage
      3. Per-item: compute_can_delete → permission check (fail fast)
      4. Fetch names for result messages
      5. Single transaction: delete_personas → bulk delete
      6. invalidate_tags
    """

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            # Confirm deletion: no-op (already deactivated by soft delete)
            pass
        else:
            # Reject: restore soft-deleted artifact
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await restore_artifacts(
                        conn, table="persona_artifact", ids=[idempotency_key],
                    )
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["personas_mv"], operation_key=idempotency_key,
        )
        return DeletePersonaApiResponse(results=[
            DeletePersonaResult(
                success=True,
                id=idempotency_key,
                message="Delete confirmed" if accept else "Delete rejected — persona restored",
            )
        ])

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

    # ── Step 2+3: Per-item permission checks (fail fast) ──────────────

    for idx, persona_id in enumerate(persona_ids):
        ctx = await resolve_persona_permissions_context(pool, persona_id)

        if not ctx.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Persona {persona_id} not found.",
            )

        if not compute_can_delete(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            persona_department_ids=ctx.department_ids,
            active_scenario_count=ctx.active_scenario_count,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to delete this persona.",
            )

    # ── Step 4: Fetch names for result messages ───────────────────────

    name_map: dict[UUID, str] = {}
    async with pool.acquire() as conn:
        artifacts = await get_personas(conn, persona_ids, names=True)
        for artifact in artifacts:
            name = "Unknown"
            if artifact.name_ids:
                name_resources = await get_names(conn, artifact.name_ids, redis)
                if name_resources:
                    name = name_resources[0].name or "Unknown"
            name_map[artifact.id] = name

    # ── Step 5: Single transaction — bulk delete ──────────────────────

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await delete_personas(conn, persona_ids, soft=soft)

    # Refresh + invalidate (via canonical refresh)
    first_id = result.deleted_ids[0] if result.deleted_ids else None
    await refresh_persona_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["personas_mv"], soft=soft,
        operation_key=idempotency_key or first_id,
    )

    results = [
        DeletePersonaResult(
            success=True,
            id=pid,
            message=f"Persona '{name_map.get(pid, 'Unknown')}' deleted (pending confirmation)" if soft
            else f"Persona '{name_map.get(pid, 'Unknown')}' deleted successfully",
        )
        for pid in result.deleted_ids
    ]

    return DeletePersonaApiResponse(results=results)
