"""Document draft logic — composable infra architecture.

Core draft function that composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. compute_can_draft — permission check
  3. Value resolution (creatable resources only) — raw value → ID
  4. create_document_draft — entry tool (append-only snapshot)
  5. refresh_document_drafts — MV refresh
  6. invalidate_tags — cache invalidation
"""

from __future__ import annotations

import uuid
from pathlib import Path
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.document.permissions import compute_can_draft
from app.infra.globals import UPLOAD_FOLDER
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.document.types import (
    DocumentDraftFormState,
    PatchDocumentDraftApiRequest,
    PatchDocumentDraftApiResponse,
    SaveDocumentFieldError,
)
from app.tools.entries.document_drafts.create import create_document_draft
from app.tools.entries.document_drafts.refresh import refresh_document_drafts
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text as create_text_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)
from app.tools.resources.names.create import create_name
from app.tools.resources.texts.create import (
    create_text as create_text_resource,
)
from app.utils.cache.invalidate_tags import invalidate_tags

# ---------------------------------------------------------------------------
# Value resolution — creatable resources only
# ---------------------------------------------------------------------------


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchDocumentDraftApiRequest,
    session_id: UUID,
) -> list[SaveDocumentFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place).

    Single-select creatables: name, description
      → value creates resource, ID replaces value (mutually exclusive).

    Multi-select creatables: files, texts
      → values create resources (full entry chain), created IDs merged with existing IDs.

    Returns a list of errors (empty if all resolved).
    """
    errors: list[SaveDocumentFieldError] = []

    # ── Single-select creatables ──────────────────────────────────────

    if request.name is not None and request.name_id is None:
        result = await create_name(conn, request.name, redis)
        request.name_id = result.id

    if request.description is not None and request.description_id is None:
        result = await create_description(conn, request.description, redis)
        request.description_id = result.id

    # ── Multi-select creatables (merged mode) ─────────────────────────

    if request.files:
        created_ids = []
        for file_val in request.files:
            # Full chain: files_resource → files_entry (with connection) → file_uploads_entry
            file_resource = await create_file_resource(conn, redis)
            file_entry = await create_file_entry(
                conn, session_id=session_id, files_id=file_resource.id
            )
            await create_file_upload(
                conn,
                file_id=file_entry.id,
                upload_id=file_val.upload_id,
                session_id=session_id,
            )
            created_ids.append(file_resource.id)
        request.file_ids = (request.file_ids or []) + created_ids

    if request.texts:
        created_ids = []
        for text_val in request.texts:
            # Write content to disk as upload
            text_uuid = uuid.uuid4()
            final_file_path = f"{text_uuid}.txt"
            final_full_path = UPLOAD_FOLDER / f"{text_uuid}.txt"
            Path(final_full_path).write_text(text_val.content, encoding="utf-8")
            size = final_full_path.stat().st_size

            # Full chain: uploads_entry → texts_resource → texts_entry → text_uploads_entry
            upload_result = await create_upload(
                conn,
                session_id=session_id,
                file_path=final_file_path,
                mime_type="text/plain",
                size=size,
            )
            text_resource = await create_text_resource(conn, redis)
            text_entry = await create_text_entry(
                conn,
                session_id=session_id,
                texts_id=text_resource.id,
            )

            # Link texts_entry ↔ uploads_entry
            await create_text_upload(
                conn,
                text_id=text_entry.id,
                upload_id=upload_result.id,
                session_id=session_id,
            )
            created_ids.append(text_resource.id)
        request.text_ids = (request.text_ids or []) + created_ids

    return errors


# ---------------------------------------------------------------------------
# patch_document_draft_impl — composable infra architecture
# ---------------------------------------------------------------------------


async def patch_document_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchDocumentDraftApiRequest,
) -> PatchDocumentDraftApiResponse:
    """Document draft using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role
      2. compute_can_draft → permission check
      3. Value resolution (creatable resources only)
      4. create_document_draft entry tool (append-only snapshot)
      5. refresh_document_drafts MV
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
            detail="You don't have permission to create or edit document drafts.",
        )

    # ── Step 3: Value resolution (creatable only) ──────────────────────

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(conn, redis, request, session_id)
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
            result = await create_document_draft(
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
                file_ids=request.file_ids,
                image_ids=request.image_ids,
                text_ids=request.text_ids,
                parameter_field_ids=request.parameter_field_ids,
                parameter_ids=request.parameter_ids,
                profile_ids=[profile.profiles_id],
            )

    # ── Step 5: Build form state (server is source of truth) ──────────

    form_state = DocumentDraftFormState(
        name_id=request.name_id,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        file_ids=request.file_ids or [],
        image_ids=request.image_ids or [],
        text_ids=request.text_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        parameter_ids=request.parameter_ids or [],
    )

    # ── Step 6: Refresh MV ─────────────────────────────────────────────

    async with pool.acquire() as conn:
        await refresh_document_drafts(conn)

    # ── Step 7: Invalidate cache ───────────────────────────────────────

    await invalidate_tags(["documents", "drafts"], redis=redis)

    return PatchDocumentDraftApiResponse(
        success=True,
        draft_id=result.id,
        new_version=new_version,
        message="Draft created successfully",
        form_state=form_state,
    )
