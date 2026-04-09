"""Document text upload logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for document:text_upload
  3. create_upload — raw file metadata (uploads_entry)
  4. create_text — semantic metadata (texts_resource)
  5. create_text_upload — link text <-> upload (text_uploads_entry)

Does NOT link the text to any document — that is a separate update operation.
"""

from __future__ import annotations

import os
import uuid as _uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.document.types import TextUploadDocumentApiResponse
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.texts.create import create_text
from app.utils.cache.invalidate_tags import invalidate_tags

ALLOWED_TEXT_TYPES = {
    "text/plain",
    "text/html",
    "text/csv",
    "text/markdown",
    "text/xml",
    "application/json",
    "application/xml",
}


async def text_upload_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    file_bytes: bytes,
    filename: str,
    content_type: str,
) -> TextUploadDocumentApiResponse:
    """Upload a text file for later use in documents.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (document:text_upload)
      3. Validate MIME type against ALLOWED_TEXT_TYPES
      4. Write file to disk
      5. create_upload -> uploads_entry
      6. create_text -> texts_resource
      7. create_text_upload -> text_uploads_entry (link)
      8. invalidate_tags
    """
    # -- Step 1: Profile context ------------------------------------------------
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check -----------------------------------------------
    if not has_permission(profile.role_permissions, "document", "text_upload"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload document texts.",
        )

    # -- Step 3: Validate MIME type ---------------------------------------------
    if content_type not in ALLOWED_TEXT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported text type: {content_type}",
        )

    # -- Step 4: Write file to disk ---------------------------------------------
    upload_uuid = _uuid.uuid4()

    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".txt"

    file_path = f"{upload_uuid}{ext}"
    full_path = UPLOAD_FOLDER / f"{upload_uuid}{ext}"

    with open(full_path, "wb") as f:
        f.write(file_bytes)

    # -- Step 5-7: DB records in single connection ------------------------------
    session_uuid = session_id or UUID(int=0)

    async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            session_id=session_uuid,
            file_path=file_path,
            mime_type=content_type,
            size=len(file_bytes),
        )

        text_result = await create_text(
            conn,
            redis,
        )

        await create_text_upload(
            conn,
            text_id=text_result.id,
            upload_id=upload_result.id,
            session_id=session_uuid,
        )

    # -- Step 8: Invalidate cache -----------------------------------------------
    await invalidate_tags(["uploads", "resources", "texts"], redis=redis)

    return TextUploadDocumentApiResponse(
        text_id=text_result.id,
        upload_id=upload_result.id,
    )
