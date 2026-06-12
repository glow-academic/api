"""Scenario video download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for scenario:video_download
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
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.upload_owner import enforce_upload_owner
from app.infra.scenario.types import VideoDownloadScenarioApiResult
from app.tools.entries.videos.search import search_videos
from app.tools.entries.videos.get import get_video


async def video_download_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    video_id: UUID,
    session_id: UUID | None = None,
) -> VideoDownloadScenarioApiResult:
    """Resolve a video resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (scenario:video_download)
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
    if not has_permission(profile.role_permissions, "scenario", "video_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download scenario videos.",
        )

    # -- Step 3: Resolve to a file via videos_mv. Accept either flavor:
    #   * ``videos_resource.id`` — what ``MediaResult.videos_id`` /
    #     ``ProducedMedia.resource_id`` surface to the model.
    #   * ``videos_entry.id``    — what ``messages_mv.video_ids`` carries
    #     for FE chat attachments (= ``video_uploads_entry.video_id``).
    # Try resource filter first, then entry filter. Same idea as
    # ``image_download_scenario_impl``.
    async with pool.acquire() as conn:
        results = await search_videos(conn, redis, videos_ids=[video_id], limit=1)
        if not results:
            results = await search_videos(conn, redis, video_ids=[video_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this video.",
        )

    # R2 ownership scope: resolve the resource's owning session and
    # require it to belong to the caller (shared enforce_upload_owner).
    async with pool.acquire() as _own_conn:
        _owner = await get_video(_own_conn, results[0].video_id, redis)
    await enforce_upload_owner(
        pool, redis,
        upload_session_id=_owner.session_id if _owner else None,
        requester=profile,
        not_found_detail="No upload found for this video.",
    )
    video_record = results[0]

    # -- Step 4: Verify file on disk --------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, video_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Video file not found on disk.")

    return VideoDownloadScenarioApiResult(
        upload_id=video_record.upload_id,
        file_path=file_path,
        content_type=video_record.mime_type,
        filename=os.path.basename(video_record.file_path),
        size=video_record.size,
    )
