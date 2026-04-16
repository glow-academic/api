"""Document draft logic — canonical surface over existing draft tools."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.document.permissions import compute_can_draft
from app.infra.document.refresh import refresh_document_impl
from app.infra.document.types import (
    DraftFormState,
    PatchDocumentDraftApiRequest,
    PatchDocumentDraftApiResponse,
    SaveDocumentFieldError,
)
from app.infra.globals import UPLOAD_FOLDER
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.sanitize import sanitize_model_kwargs
from app.tools.entries.document_drafts.create import create_document_draft
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image as create_image_entry
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text as create_text_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.search import search_descriptions
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.resources.images.create import create_image as create_image_resource
from app.tools.resources.names.create import create_name
from app.tools.resources.names.search import search_names
from app.tools.resources.texts.create import create_text as create_text_resource


async def _resolve_creatable_values(
    conn: asyncpg.Connection,
    redis: Redis,
    request: PatchDocumentDraftApiRequest,
    session_id: UUID,
) -> list[SaveDocumentFieldError]:
    """Resolve raw value fields to resource IDs (mutates request in place)."""

    errors: list[SaveDocumentFieldError] = []

    if request.name is not None and request.name_id is None:
        results = await search_names(conn, redis, search=request.name, limit_count=20, document=True)
        match = next(
            (
                item
                for item in results
                if item.name is not None and item.name.lower() == request.name.lower()
            ),
            None,
        )
        if match and match.id:
            request.name_id = match.id
        else:
            result = await create_name(conn, request.name, redis)
            request.name_id = result.id

    if request.description is not None and request.description_id is None:
        results = await search_descriptions(
            conn,
            redis,
            search=request.description,
            limit_count=20,
            document=True,
        )
        match = next(
            (
                item
                for item in results
                if item.description is not None
                and item.description.lower() == request.description.lower()
            ),
            None,
        )
        if match and match.id:
            request.description_id = match.id
        else:
            result = await create_description(conn, request.description, redis)
            request.description_id = result.id

    if request.files:
        created_ids: list[UUID] = []
        for file_val in request.files:
            file_resource = await create_file_resource(conn, redis)
            file_entry = await create_file_entry(
                conn,
                session_id=session_id,
                files_id=file_resource.id,
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
        created_ids: list[UUID] = []
        for text_val in request.texts:
            text_uuid = uuid.uuid4()
            final_file_path = f"{text_uuid}.txt"
            final_full_path = UPLOAD_FOLDER / final_file_path
            Path(final_full_path).write_text(text_val.content, encoding="utf-8")
            size = final_full_path.stat().st_size

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
            await create_text_upload(
                conn,
                text_id=text_entry.id,
                upload_id=upload_result.id,
                session_id=session_id,
            )
            created_ids.append(text_resource.id)
        request.text_ids = (request.text_ids or []) + created_ids

    if request.images:
        created_ids: list[UUID] = []
        for image_val in request.images:
            image_resource = await create_image_resource(
                conn,
                image_val.name,
                image_val.description,
                redis,
            )
            image_entry = await create_image_entry(
                conn,
                session_id=session_id,
                images_id=image_resource.id,
            )
            if image_val.upload_id is not None:
                await create_image_upload(
                    conn,
                    image_id=image_entry.id,
                    upload_id=image_val.upload_id,
                    session_id=session_id,
                )
            created_ids.append(image_resource.id)
        request.image_ids = (request.image_ids or []) + created_ids

    return errors


async def patch_document_draft_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID,
    request: PatchDocumentDraftApiRequest | None = None,
    draft_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    **kwargs: Any,
) -> PatchDocumentDraftApiResponse:
    """Document draft using the canonical request/response contract."""

    if request is not None:
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key is not None and accept is None:
            accept = request.accept

    profile = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
    )
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found. Please sign in again.")

    if not compute_can_draft(
        role_level=profile.role_level,
        role_permissions=profile.role_permissions,
    ):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to create or edit document drafts.",
        )

    # The current document draft entry tool does not support persona-style
    # ON CONFLICT promotion or connection-level active=false state. Keep the
    # ack contract for the client, but make it a no-op server-side.
    if accept is not None and idempotency_key is not None:
        return PatchDocumentDraftApiResponse(
            success=True,
            draft_id=idempotency_key,
            idempotency_key=idempotency_key,
            message="Draft accepted" if accept else "Draft rejected",
            form_state=DraftFormState(),
        )

    if request is None:
        filtered = sanitize_model_kwargs(
            kwargs,
            list_fields={
                "files",
                "file_ids",
                "texts",
                "text_ids",
                "images",
                "flag_ids",
                "department_ids",
                "image_ids",
                "parameter_field_ids",
                "parameter_ids",
                "pending_ids",
            },
            value_id_pairs=[
                ("name", "name_id"),
                ("description", "description_id"),
            ],
        )
        if draft_id is not None:
            filtered["draft_id"] = draft_id
            filtered["input_draft_id"] = draft_id
        request = PatchDocumentDraftApiRequest(**filtered)

    if draft_id is not None and request.draft_id is None:
        request.draft_id = draft_id
    if draft_id is not None and request.input_draft_id is None:
        request.input_draft_id = draft_id

    async with pool.acquire() as conn:
        errors = await _resolve_creatable_values(conn, redis, request, session_id)
    if errors:
        raise HTTPException(status_code=400, detail=[error.model_dump() for error in errors])

    operation_key = idempotency_key or uuid.uuid4()

    async with pool.acquire() as conn:
        async with conn.transaction():
            result = await create_document_draft(
                conn,
                session_id=session_id,
                id=operation_key,
                soft=soft,
                name_ids=[request.name_id] if request.name_id else None,
                description_ids=[request.description_id] if request.description_id else None,
                flag_ids=request.flag_ids,
                department_ids=request.department_ids,
                file_ids=request.file_ids,
                image_ids=request.image_ids,
                text_ids=request.text_ids,
                parameter_field_ids=request.parameter_field_ids,
                parameter_ids=request.parameter_ids,
                profile_ids=[profile.profiles_id],
            )

    form_state = DraftFormState(
        name=None if request.name_id else request.name,
        name_id=request.name_id,
        description=None if request.description_id else request.description,
        description_id=request.description_id,
        flag_ids=request.flag_ids or [],
        department_ids=request.department_ids or [],
        file_ids=request.file_ids or [],
        image_ids=request.image_ids or [],
        text_ids=request.text_ids or [],
        parameter_field_ids=request.parameter_field_ids or [],
        parameter_ids=request.parameter_ids or [],
        pending_ids=request.pending_ids or [],
    )

    if not soft:
        await refresh_document_impl(
            pool,
            redis,
            profile_id=profile_id,
        )

    return PatchDocumentDraftApiResponse(
        success=True,
        draft_id=result.id,
        idempotency_key=operation_key,
        message="Draft created successfully",
        form_state=form_state,
    )
