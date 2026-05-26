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
from app.infra.persona.refresh import refresh_persona_impl
from app.infra.server_timing import timed
from app.infra.persona.types import (
    CreatePersonaApiRequest,
    CreatePersonaApiResponse,
    CreatePersonaItem,
    ListPersonaApiPersona,
    PersonaFieldError,
    PersonaResultItem,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.persona.create import (
    create_persona as create_persona_artifact,
)
from app.tools.artifacts.persona.get import get_personas
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "persona"


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
    request: CreatePersonaApiRequest | None = None,
    resources: list[str] | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreatePersonaApiResponse:
    """Persona bulk create using composable infra functions.

    Two call shapes:
      - First call: ``request`` (with ``personas`` items) required.
      - Ack call: ``idempotency_key`` + ``accept`` only — the dormant
        artifact is located by the operation key.

    Flow (first call):
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. Per-item denormalized snapshot (read-only hydration, outside transaction)
      5. Single transaction: create_persona_artifact per item
      6. invalidate_tags
    """
    from app.infra.persona.permissions import compute_can_create

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # ``idempotency_key`` is the originating tool call's ``calls_entry.id``.
    # The ``soft_calls_mv`` ledger holds (artifact, operation, artifact_id)
    # we need to act on; without that lookup the impl can't tell what op
    # is pending or which row to promote. See project_soft_calls_entry_pattern.
    if accept is not None and idempotency_key is not None:
        with timed("ack"):
            async with pool.acquire() as conn:
                entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
            if entry is None or entry.status != "pending" or entry.operation != "create":
                raise HTTPException(
                    status_code=404,
                    detail="No pending persona create for this call.",
                )
            target_id = entry.artifact_id

            if accept:
                # Promote: flip dormant artifact to active and create snapshot.
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await create_persona_artifact(conn, id=target_id, soft=False)

                async with pool.acquire() as conn:
                    artifacts = await get_personas(
                        conn, [target_id],
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
            # accept=False: dormant row stays (active=false). The 'rejected'
            # ledger row appended below is the canonical record; search keeps
            # filtering it out via active=false.

            async with pool.acquire() as conn:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=idempotency_key,
                    artifact=ARTIFACT,
                    operation="create",
                    artifact_id=target_id,
                    status="accepted" if accept else "rejected",
                )

        with timed("refresh"):
            await refresh_persona_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                targets=["personas_mv", "soft_calls_mv"],
            )

        return CreatePersonaApiResponse(
            results=[
                PersonaResultItem(
                    success=True,
                    id=target_id,
                    message="Persona accepted" if accept else "Persona rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── First-call requirements ───────────────────────────────────────
    if request is None or not request.personas:
        raise HTTPException(
            status_code=400,
            detail="`request.personas` is required for first-call creation "
            "(or pass `idempotency_key` + `accept` for the ack call).",
        )

    items = request.personas

    # ── Step 0: Scope fields by resources ─────────────────────────────

    if resources:
        items = [item.scoped(resources) for item in items]

    # ── Step 1: Profile context ────────────────────────────────────────

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

    # ── Step 2: Permission check ───────────────────────────────────────

    with timed("permissions"):
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

    with timed("resolve_values"):
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
        with timed("snapshot"):
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

    with timed("db_write"):
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

                    # Soft writes append a pending ledger row tied to the
                    # originating tool call so ack lookups can resolve
                    # (artifact, operation, artifact_id). idempotency_key here
                    # is the calls_entry.id (see execute_infra_operation).
                    # idempotency_key is the calls_entry.id — the route pre-mints
                    # the calls_entry with it (wrapper ``call_id=request.idempotency_key``),
                    # so this soft_call FK to calls_entry holds over HTTP too. The
                    # tool path passes idempotency_key=ctx.call_id (also a real
                    # calls_entry). Either way the FK is satisfied.
                    if soft and idempotency_key is not None:
                        await create_soft_call(
                            conn,
                            redis,
                            call_id=idempotency_key,
                            artifact=ARTIFACT,
                            operation="create",
                            artifact_id=result.id,
                        )

                    results.append(
                        PersonaResultItem(
                            success=True,
                            id=result.id,
                            message="Persona created (pending acceptance)" if soft else "Persona created successfully",
                        )
                    )

    # ── Step 6: Refresh + invalidate (via canonical refresh) ────────────

    with timed("refresh"):
        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["personas_mv", "soft_calls_mv"],
        )

    # ── Step 7: Hydrate full row content for the client ────────────────
    # See ``hydrate_persona_list_rows``: returns the same shape
    # ``/persona/search`` does. Audit framework spreads response fields
    # into ``persona.create.completed``, so the client's ghost rail can
    # materialize the new row directly without a refresh round-trip.
    # Soft-pending creates skip hydration: the dormant row isn't fully
    # active yet (denormalized snapshot is created on ack-accept).
    personas: list[ListPersonaApiPersona] | None = None
    if not soft:
        with timed("hydrate"):
            from app.infra.persona.hydrate_list_rows import hydrate_persona_list_rows
            new_ids = [r.id for r in results if r.success and r.id is not None]
            if new_ids:
                personas = await hydrate_persona_list_rows(
                    pool, redis, profile_id=profile_id, persona_ids=new_ids,
                )

    return CreatePersonaApiResponse(
        results=results,
        personas=personas,
        idempotency_key=idempotency_key,
    )
