"""Scenario file preview logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for scenario:file_preview
  3. search_files — resolve files_id -> file_path, mime_type, size (via files_mv)
  4. pdf_first_page_to_image_bytes — generate PNG preview of first page

Returns preview bytes. The transport layer (HTTP route / WS input)
decides how to serve them (raw PNG vs base64).
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
from app.infra.server_timing import timed
from app.infra.scenario.types import FilePreviewScenarioApiResult
from app.infra.upload_owner import enforce_upload_owner
from app.tools.entries.files.search import search_files
from app.tools.entries.files.get import get_file
from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)
from app.utils.mime.get_content_type import get_content_type


async def file_preview_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> FilePreviewScenarioApiResult:
    """Generate a PNG preview of a file resource (PDF first page).

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (scenario:file_preview)
      3. search_files(files_ids=[file_id]) -> file_path, mime_type, size
      4. Verify file exists and is PDF
      5. pdf_first_page_to_image_bytes -> PNG bytes
    """
    # -- Step 1: Profile context ------------------------------------------------
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check -----------------------------------------------
    with timed("permissions"):
        if not has_permission(profile.role_permissions, "scenario", "file_preview"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to preview scenario files.",
            )

    # -- Step 3: Resolve files_id -> file metadata via files_mv ----------------
    with timed("query"):
      async with pool.acquire() as conn:
        results = await search_files(conn, redis, files_ids=[file_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this file.",
        )

    # R2 ownership scope (C2): the *_preview class renders the same
    # session-owned upload bytes by caller-supplied id as the *_download class,
    # so it needs the identical guard. Resolve the resource's owning session and
    # require it to belong to the caller (shared enforce_upload_owner; 404 — not
    # 403 — to keep a denied probe indistinguishable from a missing resource).
    async with pool.acquire() as _own_conn:
        _owner = await get_file(_own_conn, results[0].file_id, redis)
    await enforce_upload_owner(
        pool, redis,
        upload_session_id=_owner.session_id if _owner else None,
        requester=profile,
        not_found_detail="No upload found for this file.",
    )
    file_record = results[0]

    # -- Step 4: Verify file on disk and is PDF ---------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, file_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    content_type = get_content_type(file_record.file_path or "", file_record.mime_type or "")
    if content_type != "application/pdf":
        raise HTTPException(
            status_code=400, detail="Preview only supported for PDF files."
        )

    # -- Step 5: Generate preview -----------------------------------------------
    with timed("render"):
        preview_bytes = pdf_first_page_to_image_bytes(file_path)
    if not preview_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate preview.")

    return FilePreviewScenarioApiResult(
        preview_bytes=preview_bytes,
        upload_id=file_record.upload_id,
    )
