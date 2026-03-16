"""Model draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_model_draft — entry tool (append-only snapshot)
  5. refresh_model_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.model.permissions import compute_can_draft
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.model.types import (
    ModelDraftFormState,
    PatchModelDraftApiRequest,
    PatchModelDraftApiResponse,
    SaveModelFieldError,
)
from app.tools.entries.model_drafts.create import create_model_draft
from app.tools.entries.model_drafts.refresh import refresh_model_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchModelDraftApiRequest,
) -> list[SaveModelFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Only handles creatable resources: name, description.
    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveModelFieldError] = []

    async with pool.acquire() as conn:
        if request.name is not None and request.name_id is None:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

        if request.description is not None and request.description_id is None:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

    return errors


# ---------------------------------------------------------------------------
# patch_model_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_model_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchModelDraftApiRequest,
) -> PatchModelDraftApiResponse:
    """Model draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_model_draft entry tool (append-only snapshot)
      5. refresh_model_drafts MV
      6. invalidate_tags
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

    if not compute_can_draft(user_role=profile.role):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit model drafts.",
        )

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 4: Create draft entry (append-only snapshot) ──────────────

    # Compute new version
    new_version = request.expected_version + 1

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_model_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                modality_ids=request.modality_ids,
                pricing_ids=request.pricing_ids,
                provider_ids=request.provider_ids,
                quality_ids=request.quality_ids,
                reasoning_level_ids=request.reasoning_level_ids,
                temperature_level_ids=request.temperature_level_ids,
                value_ids=request.value_ids,
                voice_ids=request.voice_ids,
            )

    # ── Step 5: Build form state (server is source of truth) ────────────

    form_state = ModelDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        modality_ids=request.modality_ids or [],
        pricing_ids=request.pricing_ids or [],
        provider_ids=request.provider_ids or [],
        quality_ids=request.quality_ids or [],
        reasoning_level_ids=request.reasoning_level_ids or [],
        temperature_level_ids=request.temperature_level_ids or [],
        value_ids=request.value_ids or [],
        voice_ids=request.voice_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_model_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["models", "drafts"], redis=redis)

    return PatchModelDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
