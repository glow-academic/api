"""Test call download — composable infra architecture.

Same pattern as group call download, scoped to test permissions.

TODO: Add image_download, video_download, audio_download, file_download
      as modalities expand.
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import CALL_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.upload_owner import enforce_upload_owner
from app.infra.server_timing import timed
from app.infra.test.clean_content import clean_for_grading
from app.infra.test.media_types import CallDownloadTestApiResult
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.uploads.get import get_upload


async def call_download_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    call_id: UUID | None = None,
    id: UUID | None = None,
    session_id: UUID | None = None,
    **_kwargs,
) -> CallDownloadTestApiResult:
    """Resolve a call resource to its file on disk.

    Accepts both `call_id` and `id` (canonical tool arg name).
    """
    effective_call_id = call_id or id
    if not effective_call_id:
        raise HTTPException(status_code=400, detail="call_id is required")

    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found.")

    if not has_permission(profile.role_permissions, "test", "call_download"):
        raise HTTPException(status_code=403, detail="No permission for test call download.")

    with timed("hydrate"):
      async with pool.acquire() as conn:
        junctions = await search_call_uploads(conn, redis, call_ids=[effective_call_id], limit=1)
        if not junctions:
            raise HTTPException(status_code=404, detail="No upload found for this call.")

        await enforce_upload_owner(
            pool, redis,
            upload_session_id=junctions[0].session_id,
            requester=profile,
            not_found_detail="No upload found for this call.",
        )
        upload = await get_upload(conn, junctions[0].upload_id, redis)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    file_path = os.path.join(CALL_FOLDER, upload.file_path)
    if not os.path.exists(file_path):
        # Fallback to UPLOAD_FOLDER
        from app.infra.globals import UPLOAD_FOLDER
        file_path = os.path.join(UPLOAD_FOLDER, upload.file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Call file not found on disk.")

    # Read and clean file content for AI executor consumption
    content = ""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = clean_for_grading(f.read())
    except Exception:
        content = "(unable to read file content)"

    return CallDownloadTestApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
        content=content,
    )
