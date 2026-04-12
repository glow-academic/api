"""Test text download — composable infra architecture.

Same pattern as group text download, scoped to test permissions.

TODO: Add image_download, video_download, audio_download, file_download
      as modalities expand.
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.infra.test.media_types import TextDownloadTestApiResult
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.text_uploads.search import search_text_uploads
from app.tools.entries.uploads.get import get_upload


async def text_download_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    text_id: UUID | None = None,
    id: UUID | None = None,
    session_id: UUID | None = None,
    **_kwargs,
) -> TextDownloadTestApiResult:
    """Resolve a text resource to its file on disk.

    Accepts both `text_id` and `id` (canonical tool arg name).
    """
    effective_text_id = text_id or id
    if not effective_text_id:
        raise HTTPException(status_code=400, detail="text_id is required")

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found.")

    if not has_permission(profile.role_permissions, "test", "text_download"):
        raise HTTPException(status_code=403, detail="No permission for test text download.")

    async with pool.acquire() as conn:
        junctions = await search_text_uploads(conn, text_ids=[effective_text_id], limit=1)
        if not junctions:
            raise HTTPException(status_code=404, detail="No upload found for this text.")

        upload = await get_upload(conn, junctions[0].upload_id)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    file_path = os.path.join(UPLOAD_FOLDER, upload.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Text file not found on disk.")

    return TextDownloadTestApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
    )
