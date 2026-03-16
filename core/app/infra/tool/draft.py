"""Tool draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_tool_draft — entry tool (append-only snapshot)
  5. refresh_tool_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tool.permissions import compute_can_draft
from app.infra.tool.types import (
    PatchToolDraftApiRequest,
    PatchToolDraftApiResponse,
    SaveToolFieldError,
    ToolDraftFormState,
)
from app.tools.entries.tool_drafts.create import create_tool_draft
from app.tools.entries.tool_drafts.refresh import refresh_tool_drafts
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.names.create import create_name
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchToolDraftApiRequest,
) -> list[SaveToolFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Only handles creatable resources: name, description.
    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveToolFieldError] = []

    if request.name is not None and request.name_id is None:
        result = await create_name(conn, request.name, redis)
        request.name_id = result.id

    if request.description is not None and request.description_id is None:
        result = await create_description(conn, request.description, redis)
        request.description_id = result.id

    return errors


# ---------------------------------------------------------------------------
# patch_tool_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_tool_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchToolDraftApiRequest,
) -> PatchToolDraftApiResponse:
    """Tool draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_tool_draft entry tool (append-only snapshot)
      5. refresh_tool_drafts MV
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
            detail="You don't have permission to create or edit tool drafts.",
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
            result = await create_tool_draft(
                conn,
                group_id=profile.group_id,
                session_id=session_id,
                version=new_version,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id]
                if request.description_id
                else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                arg_ids=request.arg_ids,
                arg_position_ids=request.arg_position_ids,
                args_output_ids=request.args_output_ids,
                artifact_ids=request.artifact_ids,
                operation_ids=request.operation_ids,
                profile_ids=[profile.profiles_id],
            )

    # ── Step 5: Build form state (server is source of truth) ────────────

    form_state = ToolDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        arg_ids=request.arg_ids or [],
        arg_position_ids=request.arg_position_ids or [],
        args_output_ids=request.args_output_ids or [],
        artifact_ids=request.artifact_ids or [],
        operation_ids=request.operation_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_tool_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["tools", "drafts"], redis=redis)

    return PatchToolDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
