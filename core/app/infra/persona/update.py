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
from app.infra.persona.refresh import refresh_persona_impl
from app.infra.persona.types import (
    ListPersonaApiPersona,
    UpdatePersonaApiRequest,
    UpdatePersonaApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.update import (
    _UNSET,
)
from app.tools.artifacts.persona.update import (
    update_persona as update_persona_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "persona"


async def update_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdatePersonaApiRequest | None = None,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdatePersonaApiResponse:
    """Persona bulk update using composable infra functions.

    Two call shapes:
      - First call: ``request`` (with ``personas`` items) required.
      - Ack call: ``idempotency_key`` + ``accept`` only — the dormant
        update is located by the operation key.

    Flow (first call):
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
    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Short-circuit: ack path ───────────────────────────────────────
    # ``idempotency_key`` is the originating tool call's ``calls_entry.id``.
    # Look up the ledger row to resolve the dormant update's artifact_id.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending persona update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            # Promote: re-call update with soft=False → activates artifact + junctions.
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_persona_artifact(
                        conn, target_id, soft=False,
                    )

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
        # accept=False: dormant junction changes stay in place; the
        # 'rejected' ledger row appended below is the canonical record.

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )

        await refresh_persona_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=["personas_mv", "soft_calls_mv"], operation_key=idempotency_key,
        )

        return UpdatePersonaApiResponse(
            results=[
                PersonaResultItem(
                    success=True,
                    id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # persona matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[PersonaResultItem] = []

    if request is not None and request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.persona.resolve_matching_ids import resolve_matching_persona_ids
        from app.infra.persona.types import UpdatePersonaItem

        matching = await resolve_matching_persona_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            scenario_ids=request.scenario_ids,
            field_ids=request.field_ids,
            filter_department_ids=request.filter_department_ids,
            scenario_search=request.scenario_search,
            field_search=request.field_search,
            department_search=request.department_search,
            color_search=request.color_search,
            icon_search=request.icon_search,
            voice_search=request.voice_search,
            instruction_search=request.instruction_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [pid for pid in matching if pid not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdatePersonaApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdatePersonaItem(id=pid, **patch_fields) for pid in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"personas": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if request is None or not request.personas:
        raise HTTPException(
            status_code=400,
            detail="`request.personas` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

    items = request.personas

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

    # ── Step 2: Per-item permission check ──────────────────────────────
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = request is not None and request.all
    permitted_items: list = []

    for idx, item in enumerate(items):
        perms = await resolve_persona_permissions_context(pool, item.id)
        if not perms.exists:
            if is_all_matching:
                skipped_results.append(PersonaResultItem(
                    success=False, id=item.id,
                    message=f"Persona {item.id} not found (skipped)",
                ))
                continue
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
            if is_all_matching:
                skipped_results.append(PersonaResultItem(
                    success=False, id=item.id,
                    message=f"No permission to update persona {item.id} (skipped)",
                ))
                continue
            raise HTTPException(
                status_code=403,
                detail=f"Item {idx}: You don't have permission to update this persona.",
            )

        permitted_items.append(item)

    # All-matching path: filter ``items`` to permitted rows only. The
    # explicit path leaves it untouched (it already raised on any
    # failure).
    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdatePersonaApiResponse(
                results=skipped_results,
                idempotency_key=idempotency_key,
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
                    flag_ids=item.flag_ids or None,
                    parameter_field_ids=item.parameter_field_ids,
                    persona_ids=[personas_resource_id] if personas_resource_id else None,
                    voice_ids=item.voice_ids,
                    soft=soft,
                )

                # Pending ledger row tied to this tool call (see create.py
                # for the full pattern + reasoning).
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
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

    # ── Hydrate full row content for the client ──────────────────────
    personas: list[ListPersonaApiPersona] | None = None
    if not soft:
        from app.infra.persona.hydrate_list_rows import hydrate_persona_list_rows
        updated_ids = [r.id for r in results if r.success and r.id is not None]
        if updated_ids:
            personas = await hydrate_persona_list_rows(
                pool, redis, profile_id=profile_id, persona_ids=updated_ids,
            )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdatePersonaApiResponse(
        results=results + skipped_results,
        personas=personas,
        idempotency_key=idempotency_key,
    )
