"""Attempt file preview logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for attempt:file_preview
  3. search_file_uploads — resolve file_id -> upload_id
  4. get_upload — resolve upload_id -> file_path, mime_type, size
  5. pdf_first_page_to_image_bytes — generate PNG preview

Returns raw PNG bytes. The transport layer (HTTP route) wraps in Response.
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.file_uploads.search import search_file_uploads
from app.tools.entries.uploads.get import get_upload
from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)
from app.utils.mime.get_content_type import get_content_type


async def file_preview_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> bytes:
    """Generate a PNG preview of the first page of a PDF file.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (attempt:file_preview)
      3. search_file_uploads(file_ids=[file_id]) -> upload_id
      4. get_upload(upload_id) -> file_path, mime_type, size
      5. Verify file exists and is PDF
      6. Generate preview bytes
    """
    # -- Step 1: Profile context -----------------------------------------------
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check ----------------------------------------------
    if not has_permission(profile.role_permissions, "attempt", "file_preview"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to preview attempt files.",
        )

    # -- Step 3: Resolve file_id -> upload_id ----------------------------------
    async with pool.acquire() as conn:
        junctions = await search_file_uploads(conn, file_ids=[file_id], limit=1)

        if not junctions:
            raise HTTPException(
                status_code=404,
                detail="No upload found for this file.",
            )

        upload_id = junctions[0].upload_id

        # -- Step 4: Resolve upload_id -> file metadata ------------------------
        upload = await get_upload(conn, upload_id)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    # -- Step 5: Verify file on disk -------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, upload.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    content_type = get_content_type(upload.file_path or "", upload.mime_type or "")
    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400, detail="Preview only supported for PDF files",
        )

    # -- Step 6: Generate preview bytes ----------------------------------------
    preview_bytes = pdf_first_page_to_image_bytes(file_path)
    if not preview_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate preview")

    return preview_bytes
