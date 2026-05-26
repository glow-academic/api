"""Group image download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for group:image_download
  3. search_images — resolve images_id (resource) -> file_path, mime_type, size

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
from app.infra.group.media_types import ImageDownloadGroupApiResult
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.images.search import search_images


async def image_download_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    image_id: UUID,
    session_id: UUID | None = None,
) -> ImageDownloadGroupApiResult:
    """Resolve an image resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (group:image_download)
      3. search_images(images_ids=[image_id]) -> file_path, mime_type, size
      4. Verify file exists on disk
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
    if not has_permission(profile.role_permissions, "system", "image_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download group images.",
        )

    # -- Step 3: Resolve id -> file metadata via images_mv ----------------------
    # ``image_id`` may arrive as either an ``images_entry.id`` (what
    # ``messages_mv.image_ids`` aggregates from ``image_uploads_entry``
    # — the chat MV path used by the Group panel bubbles) or an
    # ``images_resource.id`` (what ``MediaResult.images_id`` and the
    # scenario picker surface). ``search_images`` accepts both filter
    # slots; try the entry path first, fall back to the resource path.
    with timed("hydrate"):
      async with pool.acquire() as conn:
        results = await search_images(conn, redis, image_ids=[image_id], limit=1)
        if not results:
            results = await search_images(conn, redis, images_ids=[image_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this image.",
        )

    image_record = results[0]

    # -- Step 4: Verify file on disk --------------------------------------------
    file_path = os.path.join(UPLOAD_FOLDER, image_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")

    return ImageDownloadGroupApiResult(
        upload_id=image_record.upload_id,
        file_path=file_path,
        content_type=image_record.mime_type,
        filename=os.path.basename(image_record.file_path),
        size=image_record.size,
    )
