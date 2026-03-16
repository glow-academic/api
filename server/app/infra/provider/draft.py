"""Provider draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_provider_draft — entry tool (append-only snapshot)
  5. refresh_provider_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import compute_can_draft
from app.infra.provider.types import (
    PatchProviderDraftApiRequest,
    PatchProviderDraftApiResponse,
    ProviderDraftFormState,
    SaveProviderFieldError,
)
from app.tools.entries.provider_drafts.create import create_provider_draft
from app.tools.entries.provider_drafts.refresh import refresh_provider_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    conn: asyncpg.Connection | asyncpg.Pool,
    redis: Redis,
    request: PatchProviderDraftApiRequest,
) -> list[SaveProviderFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Only handles creatable resources: name, description.
    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveProviderFieldError] = []

    if request.name is not None and request.name_id is None:
        result = await create_name(conn, request.name, redis)
        request.name_id = result.id

    if request.description is not None and request.description_id is None:
        result = await create_description(conn, request.description, redis)
        request.description_id = result.id

    return errors


# ---------------------------------------------------------------------------
# patch_provider_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_provider_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchProviderDraftApiRequest,
) -> PatchProviderDraftApiResponse:
    """Provider draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_provider_draft entry tool (append-only snapshot)
      5. refresh_provider_drafts MV
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
            detail="You don't have permission to create or edit provider drafts.",
        )

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(conn, redis, request)
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
            result = await create_provider_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                profile_ids=[profile.profiles_id],
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=[request.flag_id] if request.flag_id else None,
                department_ids=request.department_ids,
                endpoint_ids=request.endpoint_ids,
                key_ids=request.key_ids,
                value_ids=request.value_ids,
            )

    # ── Step 5: Build form state (server is source of truth) ────────────

    form_state = ProviderDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_id=request.flag_id,
        department_ids=request.department_ids or [],
        endpoint_ids=request.endpoint_ids or [],
        key_ids=request.key_ids or [],
        value_ids=request.value_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_provider_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["providers", "drafts"], redis=redis)

    return PatchProviderDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
