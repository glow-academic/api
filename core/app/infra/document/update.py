"""Document update logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. resolve_document_permissions_context — per-item access + edit check
  3. resolve_document_values — raw value → ID resolution
  4. update_document_artifact — junction writes (partial update)
  5. create_denormalized_snapshot — documents_resource snapshot
  6. refresh_document_impl — canonical refresh + cache invalidation
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
from app.infra.document.refresh import refresh_document_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.update import (
    _UNSET,
)
from app.tools.artifacts.document.update import (
    update_document as update_document_artifact,
)
from app.infra.document.types import UpdateDocumentApiRequest, UpdateDocumentApiResponse
from app.tools.resources.flags.get import get_flags


async def _item_is_template(
    pool: asyncpg.Pool,
    redis: Redis,
    flag_ids: list[UUID] | None,
) -> bool:
    """Return True if any flag_id in the list resolves to a template flag row."""
    if not flag_ids:
        return False
    async with pool.acquire() as conn:
        rows = await get_flags(conn, list(flag_ids), redis, bypass_cache=True)
    return any(
        (getattr(row, "type", None) == "template" and getattr(row, "value", None) is True)
        for row in rows
    )


async def update_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: UpdateDocumentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> UpdateDocumentApiResponse:
    """Document bulk update using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. Per-item: resolve_document_permissions_context → exists + compute_can_edit
      3. ACK short-circuit for dormant update promotion/rejection
      4. Per-item value resolution (raw → ID, no required field enforcement)
      5. Single transaction: update_document_artifact + denormalized snapshot per item
      6. canonical refresh
    """
    from app.infra.document.permissions import compute_can_edit
    from app.infra.document.types import (
        DocumentResultItem,
    )

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    items = request.documents

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

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_document_permissions_context(conn, item.id)
            if not perms.exists:
                raise HTTPException(
                    status_code=404,
                    detail=f"Item {idx}: Document {item.id} not found.",
                )
            if not compute_can_edit(
                role_level=profile.role_level, role_permissions=profile.role_permissions,
                document_department_ids=perms.department_ids,
                active_scenario_count=perms.active_scenario_count,
                user_department_ids=profile.department_ids,
            ):
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this document.",
                )

    # ── Step 3: ACK short-circuit ──────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_document_artifact(
                        conn,
                        idempotency_key,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_documents(
                    conn,
                    [idempotency_key],
                    names=True,
                    descriptions=True,
                    departments=True,
                    flags=True,
                    images=True,
                    parameter_fields=True,
                )
            if artifacts:
                artifact = artifacts[0]
                template = False
                if artifact.flag_ids:
                    async with pool.acquire() as conn:
                        flag_artifacts = await get_flags(
                            conn,
                            list(artifact.flag_ids),
                            redis,
                            bypass_cache=True,
                        )
                    template = any(flag.type == "template" for flag in flag_artifacts)

                await create_denormalized_snapshot(
                    pool,
                    redis,
                    name_id=artifact.name_ids[0] if artifact.name_ids else None,
                    description_id=artifact.description_ids[0] if artifact.description_ids else None,
                    department_ids=artifact.department_ids or None,
                    image_ids=artifact.images_ids or None,
                    parameter_field_ids=artifact.parameter_field_ids or None,
                    template=template,
                )

            await refresh_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                operation_key=idempotency_key,
            )

        return UpdateDocumentApiResponse(
            results=[
                DocumentResultItem(
                    success=True,
                    document_id=idempotency_key,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 4: Per-item value resolution ──────────────────────────────

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
        return UpdateDocumentApiResponse(
            results=error_results,
            idempotency_key=idempotency_key,
        )

    # ── Step 5: Single transaction ─────────────────────────────────────

    results: list[DocumentResultItem] = []

    for item in items:
        documents_resource_id = None
        if not soft:
            template = await _item_is_template(pool, redis, item.flag_ids)
            documents_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                image_ids=item.image_ids,
                parameter_field_ids=item.parameter_field_ids,
                template=template,
            )

        flag_ids = list(item.flag_ids) if item.flag_ids else None

        async with pool.acquire() as conn:
            async with conn.transaction():
                await update_document_artifact(
                    conn,
                    item.id,
                    name_id=item.name_id if item.name_id else _UNSET,
                    description_id=item.description_id if item.description_id else _UNSET,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    file_ids=item.upload_ids,
                    image_ids=item.image_ids,
                    parameter_field_ids=item.parameter_field_ids,
                    text_ids=item.text_ids,
                    document_ids=[documents_resource_id] if documents_resource_id else None,
                    soft=soft,
                )

        results.append(
            DocumentResultItem(
                success=True,
                document_id=item.id,
                message="Document updated (pending acceptance)" if soft else "Document updated successfully",
            )
        )

    # ── Step 6: Canonical refresh ──────────────────────────────────────

    await refresh_document_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].document_id if results else None),
    )

    return UpdateDocumentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
