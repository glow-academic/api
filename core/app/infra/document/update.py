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
from app.infra.document.types import UpdateDocumentApiRequest, UpdateDocumentApiResponse
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.update import (
    _UNSET,
)
from app.tools.artifacts.document.update import (
    update_document as update_document_artifact,
)
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.soft_calls.refresh import refresh_soft_calls
from app.tools.resources.flags.get import get_flags

ARTIFACT = "document"


async def _item_is_template(
    pool: asyncpg.Pool,
    redis: Redis,
    flag_ids: list[UUID] | None,
) -> bool:
    """Return True if any flag_id in the list resolves to a template flag row."""
    if not flag_ids:
        return False
    rows = await get_flags(pool, list(flag_ids), redis, bypass_cache=True)
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

    Three call shapes:
      - First call (explicit): ``request.documents`` required.
      - First call (all-matching): ``request.all=true`` plus ``patch``
        plus filter fields. The impl resolves matching ids, clones
        the patch per id (stamping each id), then runs the existing
        per-row update flow. Per-row permission failures soft-skip.
      - Ack call: ``idempotency_key`` + ``accept`` only.

    Flow (first call):
      1. (all-matching only) resolve_matching_document_ids → synth items
      2. resolve_profile_identity_context → role, department_ids
      3. Per-item: resolve_document_permissions_context → exists + compute_can_edit
      4. ACK short-circuit for dormant update promotion/rejection
      5. Per-item value resolution (raw → ID, no required field enforcement)
      6. Single transaction: update_document_artifact + denormalized snapshot per item
      7. canonical refresh
    """
    from app.infra.document.permissions import compute_can_edit
    from app.infra.document.types import (
        DocumentResultItem,
    )

    # ── Merge ack fields from request (HTTP) or params (generation pipeline)
    idempotency_key = idempotency_key or request.idempotency_key
    if idempotency_key and accept is None:
        accept = request.accept

    # ── ACK short-circuit FIRST (mirrors persona/scenario) ─────────────
    # Permission checks below assume real items; under ack we just
    # promote/reject the dormant artifact, no items list to iterate.
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != "update":
            raise HTTPException(
                status_code=404,
                detail="No pending document update for this call.",
            )
        target_id = entry.artifact_id

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await update_document_artifact(
                        conn,
                        target_id,
                        soft=False,
                    )

            async with pool.acquire() as conn:
                artifacts = await get_documents(
                    conn,
                    [target_id],
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
                    flag_artifacts = await get_flags(pool,
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

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation="update",
                artifact_id=target_id,
                status="accepted" if accept else "rejected",
            )
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

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
                    document_id=target_id,
                    message="Update accepted" if accept else "Update rejected",
                )
            ],
            idempotency_key=idempotency_key,
        )

    # ── All-matching path: resolve ids + synthesize per-row items ─────
    # Past the ack short-circuit and ``all=true`` ⇒ enumerate every
    # document matching the filter, then clone ``request.patch`` per
    # id (stamping the resolved id). The downstream per-row flow runs
    # unchanged. Per-row permission failures soft-skip (collected into
    # ``skipped_results`` and threaded into the final response).
    skipped_results: list[DocumentResultItem] = []

    if request.all:
        if request.patch is None:
            raise HTTPException(
                status_code=400,
                detail="`patch` is required when `all=true` "
                "(it carries the shared change set applied to every matched row).",
            )
        from app.infra.document.resolve_matching_ids import resolve_matching_document_ids
        from app.infra.document.types import UpdateDocumentItem

        matching = await resolve_matching_document_ids(
            pool, redis,
            profile_id=profile_id,
            search=request.search,
            scenario_ids=request.scenario_ids,
            field_ids=request.field_ids,
            filter_department_ids=request.filter_department_ids,
            scenario_search=request.scenario_search,
            field_search=request.field_search,
            department_search=request.department_search,
            flag_search=request.flag_search,
        )
        excluded = set(request.excluded_ids or [])
        resolved_ids = [did for did in matching if did not in excluded]

        if not resolved_ids:
            # Empty matching set — well-formed intent, just no rows.
            return UpdateDocumentApiResponse(results=[], idempotency_key=idempotency_key)

        # Clone the patch per matched row, stamping the resolved id.
        # ``model_dump(exclude_unset=True, exclude={"id"})`` keeps sparse
        # semantics — only fields the client actually set are written.
        patch_fields = request.patch.model_dump(exclude_unset=True, exclude={"id"})
        synth_items = [UpdateDocumentItem(id=did, **patch_fields) for did in resolved_ids]
        # Splice into the request shape downstream code expects.
        request = request.model_copy(update={"documents": synth_items})

    # ── First-call requirements ───────────────────────────────────────
    if not request.documents:
        raise HTTPException(
            status_code=400,
            detail="`request.documents` is required for first-call update "
            "(or pass `idempotency_key` + `accept` for the ack call, "
            "or `all=true` with `patch` and filter fields).",
        )

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
    # Explicit path fails fast (existing behavior).
    # All-matching path soft-skips so the response carries per-row
    # outcomes without aborting rows the user CAN edit.
    is_all_matching = bool(request.all)
    permitted_items: list = []

    async with pool.acquire() as conn:
        for idx, item in enumerate(items):
            perms = await resolve_document_permissions_context(conn, item.id)
            if not perms.exists:
                if is_all_matching:
                    skipped_results.append(DocumentResultItem(
                        success=False, document_id=item.id,
                        message=f"Document {item.id} not found (skipped)",
                    ))
                    continue
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
                if is_all_matching:
                    skipped_results.append(DocumentResultItem(
                        success=False, document_id=item.id,
                        message=f"No permission to update document {item.id} (skipped)",
                    ))
                    continue
                raise HTTPException(
                    status_code=403,
                    detail=f"Item {idx}: You don't have permission to update this document.",
                )

            permitted_items.append(item)

    if is_all_matching:
        items = permitted_items
        if not items:
            return UpdateDocumentApiResponse(
                results=skipped_results,
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

                # Pending ledger row tied to this tool call.
                if soft and idempotency_key is not None:
                    await create_soft_call(
                        conn,
                        redis,
                        call_id=idempotency_key,
                        artifact=ARTIFACT,
                        operation="update",
                        artifact_id=item.id,
                    )

        results.append(
            DocumentResultItem(
                success=True,
                document_id=item.id,
                message="Document updated (pending acceptance)" if soft else "Document updated successfully",
            )
        )

    # ── Step 6: Canonical refresh ──────────────────────────────────────

    if soft and idempotency_key is not None:
        async with pool.acquire() as conn:
            await refresh_soft_calls(conn)

    await refresh_document_impl(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        soft=soft,
        operation_key=idempotency_key or (results[0].document_id if results else None),
    )

    # All-matching path threads soft-skipped rows back into the
    # response so the client can surface "X updated, Y skipped" in
    # one toast. Explicit path's ``skipped_results`` is empty.
    return UpdateDocumentApiResponse(
        results=results + skipped_results,
        idempotency_key=idempotency_key,
    )
