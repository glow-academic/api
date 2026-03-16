"""Document update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_document_permissions_context — per-item access + edit check
  3. resolve_document_values — raw value → ID resolution
  4. update_document_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — documents_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.document.permissions_context import (
    create_denormalized_snapshot,
    resolve_document_permissions_context,
    resolve_document_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.document.update import (
    _UNSET,
)
from app.tools.artifacts.document.update import (
    update_document as update_document_artifact,
)
from app.utils.cache.invalidate_tags import invalidate_tags


async def update_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    items: list,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
) -> dict:
    """Document bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_document_permissions_context → exists + compute_can_edit
      3. Per-item value resolution (raw → ID, no required field enforcement)
      4. Single transaction: update_document_artifact + denormalized snapshot per item
      5. invalidate_tags
    """
    from app.infra.document.permissions import compute_can_edit
    from app.infra.document.types import (
        DocumentResultItem,
        UpdateDocumentApiResponse,
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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_document_permissions_context(conn, item.document_id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Document {item.document_id} not found.",
                )
            if not compute_can_edit(
                user_role=profile.role,
                document_department_ids=perms.department_ids,
                active_scenario_count=perms.active_scenario_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this document.",
                )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[DocumentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_document_values(
                conn, redis, item, is_create=False
            )
            if item_errors:
                has_errors = True
                error_results.append(
                    DocumentResultItem(
                        success=False,
                        message=f"Item {idx}: Validation errors",
                        errors=item_errors,
                    )
                )
            else:
                error_results.append(
                    DocumentResultItem(success=True, message="Validated")
                )

    if has_errors:
        return UpdateDocumentApiResponse(results=error_results)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[DocumentResultItem] = []

    for item in items:
        # Create denormalized snapshot OUTSIDE transaction (read-only hydration)
        documents_resource_id = await create_denormalized_snapshot(
            pool,
            redis,
            name_id=item.name_id,
            description_id=item.description_id,
            department_ids=item.department_ids,
            image_ids=item.image_ids,
            parameter_field_ids=item.field_ids,
        )

        flag_ids = [item.flag_id] if item.flag_id else None

        # Artifact update inside transaction
        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_document_artifact(
                    conn,
                    item.document_id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id
                    if item.description_id
                    else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    file_ids=item.upload_ids,
                    image_ids=item.image_ids,
                    parameter_field_ids=item.field_ids,
                    text_ids=item.text_ids,
                    document_ids=[documents_resource_id],
                )

        results.append(
            DocumentResultItem(
                success=True,
                document_id=item.document_id,
                message="Document updated successfully",
            )
        )

    # ── Step 5: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["documents"], redis=redis)

    return UpdateDocumentApiResponse(results=results)
