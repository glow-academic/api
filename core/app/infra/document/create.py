"""Document create logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_create — permission check
  3. resolve_document_values — raw value → ID resolution
  4. create_document_artifact — junction writes
  5. create_denormalized_snapshot — documents_resource snapshot
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.document.permissions_context import (
    create_denormalized_snapshot,
    resolve_document_values,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.document.refresh import refresh_document_impl
from app.tools.artifacts.document.create import (
    create_document as create_document_artifact,
)
from app.tools.artifacts.document.get import get_documents
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
from app.infra.document.types import (
    CreateDocumentApiRequest,
    DocumentResultItem,
    CreateDocumentApiResponse,
)


async def create_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    request: CreateDocumentApiRequest,
    session_id: UUID | None = None,
    draft_id: UUID | None = None,
    group_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
) -> CreateDocumentApiResponse:
    """Document bulk create using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. compute_can_create — single check (applies to all items)
      3. Per-item value resolution (raw → ID, required field enforcement)
      4. ACK short-circuit for dormant create promotion/rejection
      5. Per-item value resolution (raw → ID, required field enforcement)
      6. Single transaction: create_document_artifact + denormalized snapshot per item
      7. Refresh via canonical document refresh
    """
    from app.infra.document.permissions import compute_can_create

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

    # ── Step 2: Permission check ───────────────────────────────────────

    requested_department_ids = [
        department_id for item in items for department_id in (item.department_ids or [])
    ]

    if not compute_can_create(role_level=profile.role_level, role_permissions=profile.role_permissions, department_ids=requested_department_ids or None):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create documents.",
        )

    # ── Short-circuit: ack path ───────────────────────────────────────

    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await create_document_artifact(
                        conn,
                        id=idempotency_key,
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
                    id=artifact.id,
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

        return CreateDocumentApiResponse(
            results=[
                DocumentResultItem(
                    success=True,
                    document_id=idempotency_key,
                    message="Document accepted" if accept else "Document rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── Step 3: Per-item value resolution ──────────────────────────────

    has_errors = False
    error_results: list[DocumentResultItem] = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            item_errors = await resolve_document_values(
                conn, redis, item, is_create=True
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
        return CreateDocumentApiResponse(results=error_results, idempotency_key=idempotency_key)

    # ── Step 4: Single transaction ─────────────────────────────────────

    results: list[DocumentResultItem] = []

    snapshot_ids: list[UUID] = []
    if not soft:
        for item in items:
            template = await _item_is_template(pool, redis, item.flag_ids)
            documents_resource_id = await create_denormalized_snapshot(
                pool,
                redis,
                id=item.resource_id,
                name_id=item.name_id,
                description_id=item.description_id,
                department_ids=item.department_ids,
                image_ids=item.image_ids,
                parameter_field_ids=item.parameter_field_ids,
                template=template,
                file_id=item.file_id,
                text_id=item.text_id,
            )
            snapshot_ids.append(documents_resource_id)

    for idx, item in enumerate(items):
        flag_ids = list(item.flag_ids) if item.flag_ids else None

        async with pool.acquire() as conn:
            async with conn.transaction():
                result = await create_document_artifact(
                    conn,
                    id=item.id,
                    name_id=item.name_id,
                    description_id=item.description_id,
                    department_ids=item.department_ids,
                    flag_ids=flag_ids,
                    file_ids=item.upload_ids,
                    image_ids=item.image_ids,
                    parameter_field_ids=item.parameter_field_ids,
                    text_ids=item.text_ids,
                    document_ids=[snapshot_ids[idx]] if snapshot_ids else None,
                    soft=soft,
                )

        results.append(
            DocumentResultItem(
                success=True,
                document_id=result.id,
                message="Document created (pending acceptance)"
                if soft
                else "Document created successfully",
            )
        )

    # ── Step 5: Canonical refresh ─────────────────────────────────────

    await refresh_document_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].document_id if results else None),
    )

    return CreateDocumentApiResponse(
        results=results,
        idempotency_key=idempotency_key,
    )
