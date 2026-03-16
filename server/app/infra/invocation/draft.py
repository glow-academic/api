"""Invocation draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Value resolution (creatable resources only) — raw value → ID
  3. create_invocation_draft — entry tool (append-only snapshot)
  4. Build form state (server is source of truth)
  5. refresh_invocation_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.invocation.types import (
    InvocationDraftFormState,
    PatchInvocationDraftApiRequest,
    PatchInvocationDraftApiResponse,
    SaveInvocationFieldError,
)
from app.tools.entries.invocation_drafts.create import (
    create_invocation_draft,
)
from app.tools.entries.invocation_drafts.refresh import (
    refresh_invocation_drafts,
)
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    pool: asyncpg.Pool,
    redis: Redis,
    request: PatchInvocationDraftApiRequest,
) -> list[SaveInvocationFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description
      → value creates resource, created ID is appended to the IDs list.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveInvocationFieldError] = []

    # ── Single-select creatables ──────────────────────────────────────

    if request.name is not None:
        async with pool.acquire() as conn:
            result = await create_name(conn, request.name, redis)
        request.name_ids = [result.id]

    if request.description is not None:
        async with pool.acquire() as conn:
            result = await create_description(conn, request.description, redis)
        request.description_ids = [result.id]

    return errors


# ---------------------------------------------------------------------------
# patch_invocation_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_invocation_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchInvocationDraftApiRequest,
) -> PatchInvocationDraftApiResponse:
    """Invocation draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. Value resolution (creatable resources only)
      3. create_invocation_draft entry tool (append-only snapshot)
      4. Build form state (server is source of truth)
      5. refresh_invocation_drafts MV
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

    # ── Step 2: Value resolution (creatable only) ──────────────────────

    errors = await _resolve_creatable_values(pool, redis, request)
    if errors:
        raise HTTPException(
            status_code=400,
            detail=[e.model_dump() for e in errors],
        )

    # ── Step 3: Create draft entry (append-only snapshot) ──────────────

    # Compute new version
    new_version = request.expected_version + 1

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_invocation_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                name_ids=request.name_ids,
                description_ids=request.description_ids,
                value_ids=request.value_ids,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                key_ids=request.key_ids,
                endpoint_ids=request.endpoint_ids,
                temperature_level_ids=request.temperature_level_ids,
                pricing_ids=request.pricing_ids,
                reasoning_level_ids=request.reasoning_level_ids,
                voice_ids=request.voice_ids,
            )

    # ── Step 4: Build form state (server is source of truth) ──────────

    form_state = InvocationDraftFormState(
        name_ids=request.name_ids or [],
        description_ids=request.description_ids or [],
        value_ids=request.value_ids or [],
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        key_ids=request.key_ids or [],
        endpoint_ids=request.endpoint_ids or [],
        temperature_level_ids=request.temperature_level_ids or [],
        pricing_ids=request.pricing_ids or [],
        reasoning_level_ids=request.reasoning_level_ids or [],
        voice_ids=request.voice_ids or [],
    )

    # ── Step 5: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_invocation_drafts(conn)

    # ── Step 6: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["benchmark", "drafts"], redis=redis)

    return PatchInvocationDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
