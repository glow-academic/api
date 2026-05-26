"""Document image download logic — composable infra architecture.

Mirror of ``app.infra.scenario.image_download``. Same composition (profile
→ permission → search_images → file_path verify); the artifact name on
the permission check is the only difference so audit events stamp
``document.image_download.*``.
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
from app.infra.document.types import ImageDownloadDocumentApiResult
from app.tools.entries.images.search import search_images


async def image_download_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    image_id: UUID,
    session_id: UUID | None = None,
) -> ImageDownloadDocumentApiResult:
    """Resolve an image resource to its file on disk for document artifacts."""
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "document", "image_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download document images.",
        )

    async with pool.acquire() as conn:
        results = await search_images(conn, redis, images_ids=[image_id], limit=1)
        if not results:
            results = await search_images(conn, redis, image_ids=[image_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this image.",
        )

    image_record = results[0]
    file_path = os.path.join(UPLOAD_FOLDER, image_record.file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Image file not found on disk.")

    return ImageDownloadDocumentApiResult(
        upload_id=image_record.upload_id,
        file_path=file_path,
        content_type=image_record.mime_type,
        filename=os.path.basename(image_record.file_path),
        size=image_record.size,
    )
