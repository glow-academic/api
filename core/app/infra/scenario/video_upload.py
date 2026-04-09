"""Scenario video upload logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for scenario:video_upload
  3. create_upload — raw file metadata (uploads_entry)
  4. create_video — semantic metadata (videos_resource)
  5. create_video_upload — link video <-> upload (video_uploads_entry)

Does NOT link the video to any scenario — that is a separate update operation.
"""

from __future__ import annotations

import os
import uuid as _uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.globals import VIDEO_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.types import VideoUploadScenarioApiResponse
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.resources.videos.create import create_video
from app.utils.cache.invalidate_tags import invalidate_tags


async def video_upload_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    name: str | None = None,
    description: str | None = None,
) -> VideoUploadScenarioApiResponse:
    """Upload a video for later use in scenarios.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (scenario:video_upload)
      3. Write file to disk
      4. create_upload -> uploads_entry
      5. create_video -> videos_resource
      6. create_video_upload -> video_uploads_entry (link)
      7. invalidate_tags
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
    if not has_permission(profile.role_permissions, "scenario", "video_upload"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload scenario videos.",
        )

    # -- Step 3: Write file to disk ---------------------------------------------
    upload_uuid = _uuid.uuid4()

    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".bin"

    relative_path = f"video/{upload_uuid}{ext}"
    full_path = VIDEO_FOLDER / f"{upload_uuid}{ext}"

    with open(full_path, "wb") as f:
        f.write(file_bytes)

    # -- Step 4-6: DB records in single connection ------------------------------
    session_uuid = session_id or UUID(int=0)
    video_name = name or os.path.splitext(filename)[0]
    video_description = description or ""

    async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            session_id=session_uuid,
            file_path=relative_path,
            mime_type=content_type,
            size=len(file_bytes),
        )

        video_result = await create_video(
            conn,
            name=video_name,
            description=video_description,
            redis=redis,
        )

        await create_video_upload(
            conn,
            video_id=video_result.id,
            upload_id=upload_result.id,
            session_id=session_uuid,
        )

    # -- Step 7: Invalidate cache -----------------------------------------------
    await invalidate_tags(["uploads", "resources", "videos"], redis=redis)

    return VideoUploadScenarioApiResponse(
        video_id=video_result.id,
        upload_id=upload_result.id,
    )
