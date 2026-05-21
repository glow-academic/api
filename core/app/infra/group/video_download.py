"""Group video download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for group:video_download
  3. search_videos — resolve videos_id (resource) -> file_path, mime_type, size

Returns resolved file metadata. The transport layer (HTTP route / WS input)
decides how to serve it (range response vs base64).
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.infra.group.media_types import VideoDownloadGroupApiResult
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.videos.search import search_videos


async def video_download_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    video_id: UUID,
    session_id: UUID | None = None,
) -> VideoDownloadGroupApiResult:
    """Resolve a video resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (group:video_download)
      3. search_videos(videos_ids=[video_id]) -> file_path, mime_type, size
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
    if not has_permission(profile.role_permissions, "system", "video_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download group videos.",
        )

    # -- Step 3: Resolve id -> file metadata via videos_mv ----------------------
    # ``video_id`` may arrive as either an ``videos_entry.id`` (what
    # ``messages_mv.video_ids`` aggregates from ``video_uploads_entry``
    # — the chat MV path used by the Group panel bubbles) or a
    # ``videos_resource.id`` (what ``MediaResult.videos_id`` /
    # ``Scenario_Generate`` surface to the LLM). ``search_videos``
    # accepts both filter slots; try the entry path first, fall back
    # to the resource path. Mirrors how the FE bubble doesn't know
    # which id-flavor the upstream surfaced it as.
    async with pool.acquire() as conn:
        results = await search_videos(conn, redis, video_ids=[video_id], limit=1)
        if not results:
            results = await search_videos(conn, redis, videos_ids=[video_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this video.",
        )

    video_record = results[0]

    # -- Step 4: Verify file on disk --------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, video_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    return VideoDownloadGroupApiResult(
        upload_id=video_record.upload_id,
        file_path=file_path,
        content_type=video_record.mime_type,
        filename=os.path.basename(video_record.file_path),
        size=video_record.size,
    )
