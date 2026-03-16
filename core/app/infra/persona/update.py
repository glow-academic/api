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
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
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
        UpdatePersonaApiResponse,
    )

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
        perms = await resolve_persona_permissions_context(pool, item.persona_id)
        if not perms.exists:
            raise HTTPException(
                status_code=404,
                detail=f"Item {idx}: Persona {item.persona_id} not found.",
            )
        if not compute_can_edit(
            user_role=profile.role,
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
                # Create denormalized snapshot
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
                    item.persona_id,
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
                    persona_ids=[personas_resource_id],
                    voice_ids=item.voice_ids,
                )

                results.append(
                    PersonaResultItem(
                        success=True,
                        persona_id=item.persona_id,
                        message="Persona updated successfully",
                    )
                )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["personas"], redis=redis)

    return UpdatePersonaApiResponse(results=results)
