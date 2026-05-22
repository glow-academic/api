"""Group audio download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for group:audio_download
  3. search_audio_uploads — resolve audio_id -> upload_id
  4. get_upload — resolve upload_id -> file_path, mime_type, size

Returns resolved file metadata. The transport layer (HTTP route / WS input)
decides how to serve it (range response vs base64).
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import AUDIO_FOLDER
from app.infra.group.media_types import AudioDownloadGroupApiResult
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.audio_uploads.search import search_audio_uploads
from app.tools.entries.uploads.get import get_upload


async def audio_download_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    audio_id: UUID,
    session_id: UUID | None = None,
) -> AudioDownloadGroupApiResult:
    """Resolve an audio resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (group:audio_download)
      3. search_audio_uploads(audio_ids=[audio_id]) -> upload_id
      4. get_upload(upload_id) -> file_path, mime_type, size
      5. Verify file exists on disk
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
    if not has_permission(profile.role_permissions, "system", "audio_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download group audio.",
        )

    # -- Step 3: Resolve audio_id -> upload_id ----------------------------------
    with timed("hydrate"):
      async with pool.acquire() as conn:
        junctions = await search_audio_uploads(conn, redis, audio_ids=[audio_id], limit=1)

        if not junctions:
            raise HTTPException(
                status_code=404,
                detail="No upload found for this audio.",
            )

        upload_id = junctions[0].upload_id

        # -- Step 4: Resolve upload_id -> file metadata -------------------------
        upload = await get_upload(conn, upload_id, redis)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    # -- Step 5: Verify file on disk --------------------------------------------
    file_path = os.path.join(AUDIO_FOLDER, os.path.basename(upload.file_path))

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")

    return AudioDownloadGroupApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
    )
