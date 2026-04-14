"""Persona update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_persona_permissions_context — per-item access + edit check
  3. resolve_persona_values — raw value → ID resolution
  4. update_persona_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — personas_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.persona.permissions_context import (
    create_denormalized_snapshot,
    resolve_persona_permissions_context,
    resolve_persona_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    UpdatePersonaApiRequest,
    UpdatePersonaApiResponse,
)
from app.infra.persona.refresh import refresh_persona_impl
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.update import (
    _UNSET,
)
from app.tools.artifacts.persona.update import (
    update_persona as update_persona_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdatePersonaApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdatePersonaApiResponse:
    """Persona bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_persona_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_persona_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.persona.permissions import compute_can_edit
    from app.infra.persona.types import (
        PersonaResultItem,
    )

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            # Promote: re-call update with soft=False → activates artifact + junctions
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_persona_artifact(
                        conn, idempotency_key, soft=False,
                    )

            # Read back junction IDs to create denormalized snapshot
            async with pool.acquire() as conn:
                artifacts = await get_personas(
                    conn, [idempotency_key],
                    names=True, descriptions=True, colors=True, icons=True,
                    instructions=True, departments=True, examples=True,
                    parameter_fields=True,
                )
            if artifacts:
                a = artifacts[0]
                await create_denormalized_snapshot(
                    pool, redis,
                    name_id=a.name_ids[0] if a.name_ids else None,
                    description_id=a.description_ids[0] if a.description_ids else None,
                    color_id=a.color_ids[0] if a.color_ids else None,
                    icon_id=a.icon_ids[0] if a.icon_ids else None,
                    instructions_id=a.instruction_ids[0] if a.instruction_ids else None,
                    department_ids=a.department_ids or None,
                    example_ids=a.example_ids or None,
                    parameter_field_ids=a.parameter_field_ids or None,
                )

            await refresh_persona_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["personas_mv"], operation_key=idempotency_key,
            )
        # accept=False: no-op (pending junction changes stay)
        return UpdatePersonaApiResponse(results=[
            PersonaResultItem(
                success=True,
                id=idempotency_key,
                message="Update accepted" if accept else "Update rejected",
            )
        ])

    items = request.personas

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=draft_id,
    )

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Per-item permission check ──────────────────────────────

    for idx, item in enumerate(items):
        perms = await resolve_persona_permissions_context(pool, item.id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Persona {item.id} not found.",
            )
        if not compute_can_edit(
            role_level=profile.role_level, role_permissions=profile.role_permissions,
            persona_department_ids=perms.department_ids,
            active_scenario_count=perms.active_scenario_count,
            user_department_ids=profile.department_ids,
        ):
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this persona.",
            )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[PersonaResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_persona_values(pool, redis, item, is_create=False)
        if item_errors:
            has_errors = True
            error_results.append(
                PersonaResultItem(
                    success=False,
                    message=f"Item {idx}: Validation errors",
                    errors=item_errors,
                )
            )
        else:
            error_results.append(PersonaResultItem(success=True, message="Validated"))

    if has_errors:
        return UpdatePersonaApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[PersonaResultItem] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for item in items:
                # Denormalized snapshot (skip when soft — dormant update)
                personas_resource_id = None
                if not soft:
                    personas_resource_id = await create_denormalized_snapshot(
                        pool,
                        redis,
                        name_id=item.name_id,
                        description_id=item.description_id,
                        color_id=item.color_id,
                        icon_id=item.icon_id,
                        instructions_id=item.instructions_id,
                        department_ids=item.department_ids,
                        example_ids=item.example_ids,
                        parameter_field_ids=item.parameter_field_ids,
                    )

                await update_persona_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    color_id=item.color_id if item.color_id else _UNSET,
                    icon_id=item.icon_id if item.icon_id else _UNSET,
                    instruction_id=item.instructions_id
                    if item.instructions_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    example_ids=item.example_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=[personas_resource_id] if personas_resource_id else None,
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

                results.append(
                    PersonaResultItem(
                        success=True,
                        id=item.id,
                        message="Persona updated (pending acceptance)" if soft else "Persona updated successfully",
                    )
                )

    # ── Step 5: Refresh + invalidate (via canonical refresh) ────────────

    first_id = results[0].id if results else None
    await refresh_persona_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["personas_mv"], soft=soft,
        operation_key=idempotency_key or first_id,
    )

    return UpdatePersonaApiResponse(results=results)
