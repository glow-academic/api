"""Persona duplicate logic — composable infra architecture.

Core duplicate function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role)
  2. compute_can_duplicate — permission check
  3. get_personas — fetch original with all junction IDs
  4. create_name — new name resource ("{name} Copy")
  5. search_flags — find inactive flag (persona_active, value=false)
  6. create_persona — new artifact with original's IDs + new name + inactive flag
  7. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.persona.permissions import compute_can_duplicate
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.persona.types import (
    DuplicatePersonaApiResponse,
)
from app.tools.artifacts.persona.create import (
    create_persona as create_persona_artifact,
)
from app.tools.artifacts.persona.get import get_personas
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names
from app.utils.cache.invalidate_tags import invalidate_tags


async def duplicate_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    persona_id: UUID,
    session_id: UUID | None = None,
) -> DuplicatePersonaApiResponse:
    """Persona duplicate using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_duplicate → permission check
      3. get_personas → fetch original with all junctions
      4. create_name("{name} Copy") → new name resource
      5. search_flags → find inactive flag (persona_active, value=false)
      6. create_persona → new artifact with original IDs + inactive flag
      7. invalidate_tags
    """

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

    if not compute_can_duplicate(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to duplicate this persona.",
        )

    # ── Step 3: Fetch original persona with all junctions ──────────────

    async with pool.acquire() as conn:
        originals = await get_personas(
            conn,
            [persona_id],
            names=True,
            descriptions=True,
            colors=True,
            icons=True,
            instructions=True,
            departments=True,
            examples=True,
            parameter_fields=True,
            voices=True,
        )

        if not originals:
            raise HTTPException(
                status_code=404,
                detail=f"Persona {persona_id} not found.",
            )

        original = originals[0]

        # ── Step 4: Create new name resource ───────────────────────────────

        original_name = "Unknown"
        if original.name_ids:
            name_resources = await get_names(conn, original.name_ids, redis)
            if name_resources:
                original_name = name_resources[0].name or "Unknown"

        new_name_resource = await create_name(conn, f"{original_name} Copy", redis)

        # ── Step 5: Find inactive flag (persona_active, value=false) ───────

        # Explicitly link the inactive flag rather than relying on absence.
        # TODO: Requires a value=false row for persona_active in flags_resource.
        # Once the seed/migration adds it, this will resolve correctly.
        inactive_flag_id: UUID | None = None
        flag_results = await search_flags(
            conn,
            redis,
            flag_type="persona_active",
            persona=True,
            limit_count=10,
        )
        inactive_match = next((f for f in flag_results if not f.value), None)
        if inactive_match:
            inactive_flag_id = inactive_match.id

    # ── Step 6: Create new persona artifact with inactive flag ─────────

    flag_ids = [inactive_flag_id] if inactive_flag_id else None

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_persona_artifact(
                conn,
                name_id=new_name_resource.id,
                description_id=original.description_ids[0]
                if original.description_ids
                else None,
                color_id=original.color_ids[0] if original.color_ids else None,
                icon_id=original.icon_ids[0] if original.icon_ids else None,
                instruction_id=original.instruction_ids[0]
                if original.instruction_ids
                else None,
                department_ids=original.department_ids,
                example_ids=original.example_ids,
                parameter_field_ids=original.parameter_field_ids,
                voice_ids=original.voice_ids,
                flag_ids=flag_ids,
            )

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["personas"], redis=redis)

    return DuplicatePersonaApiResponse(
        success=True,
        persona_id=result.id,
        message=f"Persona '{original_name}' duplicated successfully",
    )
