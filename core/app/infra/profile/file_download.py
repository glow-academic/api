"""Profile file download logic — composable infra architecture.

Mirrors infra/agent/file_download.py — file lookup is generic; only the
permission check string differs per artifact.
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile.types import FileDownloadProfileApiResult
from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.upload_owner import enforce_upload_owner
from app.infra.server_timing import timed
from app.tools.entries.files.search import search_files
from app.tools.entries.files.get import get_file


async def file_download_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> FileDownloadProfileApiResult:
    """Resolve a file resource to its file on disk."""
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "profile", "file_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download profile files.",
        )

    with timed("hydrate"):
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
    file_path = os.path.join(UPLOAD_FOLDER, file_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileDownloadProfileApiResult(
        upload_id=file_record.upload_id,
        file_path=file_path,
        content_type=file_record.mime_type,
        filename=os.path.basename(file_record.file_path),
        size=file_record.size,
    )
