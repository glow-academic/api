"""Setting file download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for setting:file_download
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

from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.setting.types import FileDownloadSettingApiResult
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.upload_owner import enforce_upload_owner
from app.tools.entries.files.search import search_files
from app.tools.entries.files.get import get_file


async def file_download_setting_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> FileDownloadSettingApiResult:
    """Resolve a file resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (setting:file_download)
      3. search_files(files_ids=[file_id]) -> file_path, mime_type, size
      4. Verify file exists on disk
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
    if not has_permission(profile.role_permissions, "setting", "file_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download setting files.",
        )

    # -- Step 3: Resolve files_id -> file metadata via files_mv ----------------
    async with pool.acquire() as conn:
        results = await search_files(conn, redis, files_ids=[file_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this file.",
        )

    # R2 ownership scope: resolve the resource's owning session and
    # require it to belong to the caller (shared enforce_upload_owner).
    async with pool.acquire() as _own_conn:
        _owner = await get_file(_own_conn, results[0].file_id, redis)
    await enforce_upload_owner(
        pool, redis,
        upload_session_id=_owner.session_id if _owner else None,
        requester=profile,
        not_found_detail="No upload found for this file.",
    )
    file_record = results[0]

    # -- Step 4: Verify file on disk --------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, file_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileDownloadSettingApiResult(
        upload_id=file_record.upload_id,
        file_path=file_path,
        content_type=file_record.mime_type,
        filename=os.path.basename(file_record.file_path),
        size=file_record.size,
    )
