"""Persona create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_persona_values — raw value → ID resolution
  4. create_persona_artifact — junction writes
  5. create_denormalized_snapshot — personas_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.persona.permissions_context import (
    create_denormalized_snapshot,
    resolve_persona_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.persona.create import (
    create_persona as create_persona_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


from app.infra.persona.types import (
    CreatePersonaItem,
    PersonaFieldError,
    PersonaResultItem,
    CreatePersonaApiResponse,
)


def _batch_department_scope(items: list[CreatePersonaItem]) -> list[str] | None:
    """Summarize whether every item is department-scoped for create permissions."""
    if not items:
        return None

    for item in items:
        if not (item.department_ids or item.departments):
            return None

    return ["department-scoped"]


async def create_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
) -> dict:
    """Persona bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Per-item denormalized snapshot (read-only hydration, outside transaction)
      5. Single transaction: create_persona_artifact per item
      6. invalidate_tags
    """
    from app.infra.persona.permissions import compute_can_create

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

    # ── Step 2: Permission check ───────────────────────────────────────

    if not compute_can_create(
        role_level=profile.role_level, role_permissions=profile.role_permissions,
        department_ids=_batch_department_scope(items),
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create personas.",
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[PersonaResultItem] = []

    for idx, item in enumerate(items):
        item_errors = await resolve_persona_values(pool, redis, item, is_create=True)
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
        return CreatePersonaApiResponse(results=error_results)

    # ── Step 4: Denormalized snapshots (read-only, outside transaction) ─

    snapshot_ids: list[UUID] = []
    for item in items:
        personas_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            id=item.resource_id,
            name_id=item.name_id,
            description_id=item.description_id,
            color_id=item.color_id,
            icon_id=item.icon_id,
            instructions_id=item.instructions_id,
            department_ids=item.department_ids,
            example_ids=item.example_ids,
            parameter_field_ids=item.parameter_field_ids,
        )
        snapshot_ids.append(personas_resource_id)

    # ── Step 5: Single transaction — artifact writes ───────────────────

    results: list[PersonaResultItem] = []

    async with pool.acquire() as conn:
        async with conn.transaction():
            for item, personas_resource_id in zip(items, snapshot_ids, strict=True):
                result = await create_persona_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    color_id=item.color_id,
                    icon_id=item.icon_id,
                    instruction_id=item.instructions_id,
                    department_ids=item.department_ids,
                    example_ids=item.example_ids,
                    flag_ids=[item.active_flag_id] if item.active_flag_id else None,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=[personas_resource_id],
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

                results.append(
                    PersonaResultItem(
                        success=True,
                        persona_id=result.id,
                        message="Persona created successfully",
                    )
                )

    # ── Step 6: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["personas"], redis=redis)

    return CreatePersonaApiResponse(results=results)
