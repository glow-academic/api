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
from app.infra.persona.refresh import refresh_persona_impl
from app.tools.artifacts.persona.create import (
    create_persona as create_persona_artifact,
)
from app.tools.artifacts.persona.get import get_personas
from app.utils.cache.invalidate_tags import invalidate_tags


from app.infra.persona.types import (
    CreatePersonaApiRequest,
    CreatePersonaApiResponse,
    CreatePersonaItem,
    PersonaFieldError,
    PersonaResultItem,
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
    request: CreatePersonaApiRequest,
    resources: list[str] | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreatePersonaApiResponse:
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

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            # Promote: re-call create with soft=False → ON CONFLICT activates
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_persona_artifact(conn, id=idempotency_key, soft=False)

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
        # accept=False: no-op (dormant artifact stays for reference)
        return CreatePersonaApiResponse(results=[
            PersonaResultItem(
                success=True,
                id=idempotency_key,
                message="Persona accepted" if accept else "Persona rejected",
            )
        ])

    items = request.personas

    # ── Step 0: Scope fields by resources ─────────────────────────────

    if resources:
        items = [item.scoped(resources) for item in items]

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

    # ── Step 4: Denormalized snapshots (skip when soft — dormant artifact) ─

    snapshot_ids: list[UUID] = []
    if not soft:
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
            for idx, item in enumerate(items):
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
                    flag_ids=item.flag_ids or None,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

                results.append(
                    PersonaResultItem(
                        success=True,
                        id=result.id,
                        message="Persona created (pending acceptance)" if soft else "Persona created successfully",
                    )
                )

    # ── Step 6: Refresh + invalidate (via canonical refresh) ────────────

    first_id = results[0].id if results else None
    await refresh_persona_impl(
        pool, redis, profile_id=profile_id, session_id=session_id,
        targets=["personas_mv"], soft=soft,
        operation_key=idempotency_key or first_id,
    )

    return CreatePersonaApiResponse(results=results)
