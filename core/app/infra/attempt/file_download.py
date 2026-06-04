"""Attempt file download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for attempt:file_download
  3. search_files — resolve files_id -> file_path, mime_type, size (via files_mv)

Returns resolved file metadata. The transport layer (HTTP route / WS input)
decides how to serve it (streaming response vs base64).
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.media_types import FileDownloadAttemptApiResult
from app.infra.attempt.permissions import enforce_attempt_media_access
from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.files.search import search_files


async def file_download_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> FileDownloadAttemptApiResult:
    """Resolve a file resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (attempt:file_download)
      3. search_files(files_ids=[file_id]) -> file_path, mime_type, size
      4. Verify file exists on disk
    """
    # -- Step 1: Profile context -----------------------------------------------
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check ----------------------------------------------
    if not has_permission(profile.role_permissions, "attempt", "file_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download attempt files.",
        )

    # -- Step 3: Resolve files_id -> file metadata via files_mv ----------------
    with timed("search_files"):
     async with pool.acquire() as conn:
        results = await search_files(conn, redis, files_ids=[file_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this file.",
        )

    file_record = results[0]

    # -- Step 3b: Per-resource access check (issue #148) -----------------------
    # The global permission above is coarse; without this any holder of
    # attempt:file_download could fetch ANY student's file by id. Resolve the
    # file's owning session and require ownership-or-higher-role, mirroring
    # get_attempt_internal's check_attempt_access gate.
    await enforce_attempt_media_access(
        pool, redis, upload_id=file_record.upload_id, requester=profile
    )

    # -- Step 4: Verify file on disk -------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, file_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileDownloadAttemptApiResult(
        upload_id=file_record.upload_id,
        file_path=file_path,
        content_type=file_record.mime_type,
        filename=os.path.basename(file_record.file_path),
        size=file_record.size,
    )
