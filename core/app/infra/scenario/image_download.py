"""Scenario image download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for scenario:image_download
  3. search_image_uploads — resolve image_id → upload_id
  4. get_upload — resolve upload_id → file_path, mime_type, size

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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.types import ImageDownloadScenarioApiResult
from app.tools.entries.image_uploads.search import search_image_uploads
from app.tools.entries.uploads.get import get_upload


async def image_download_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    image_id: UUID,
    session_id: UUID | None = None,
) -> ImageDownloadScenarioApiResult:
    """Resolve an image resource to its file on disk.

    Flow:
      1. resolve_profile_identity_context → role, permissions
      2. has_permission check (scenario:image_download)
      3. search_image_uploads(image_ids=[image_id]) → upload_id
      4. get_upload(upload_id) → file_path, mime_type, size
      5. Verify file exists on disk
    """
    # ── Step 1: Profile context ────────────────────────────────────────
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Permission check ───────────────────────────────────────
    if not has_permission(profile.role_permissions, "scenario", "image_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download scenario images.",
        )

    # ── Step 3: Resolve image_id → upload_id ───────────────────────────
    async with pool.acquire() as conn:
        junctions = await search_image_uploads(conn, image_ids=[image_id], limit=1)

        if not junctions:
            raise HTTPException(
                status_code=404,
                detail="No upload found for this image.",
            )

        upload_id = junctions[0].upload_id

        # ── Step 4: Resolve upload_id → file metadata ──────────────────
        upload = await get_upload(conn, upload_id)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    # ── Step 5: Verify file on disk ────────────────────────────────────
    file_path = os.path.join(UPLOAD_FOLDER, upload.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")

    return ImageDownloadScenarioApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
    )
