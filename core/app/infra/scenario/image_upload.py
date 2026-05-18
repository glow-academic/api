"""Scenario image upload — permission + canonical media chain.

Thin wrapper around ``media_upload_impl``:
  1. resolve_profile_identity_context
  2. has_permission("scenario", "image_upload")
  3. media_upload_impl(modality="image", ...)

Does NOT link the image to any scenario — that is a separate update.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.media.upload import media_upload_impl
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.scenario.types import ImageUploadScenarioApiResponse


async def image_upload_scenario_impl(
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
) -> ImageUploadScenarioApiResponse:
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "scenario", "image_upload"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload scenario images.",
        )

    session_uuid = session_id or profile.session_id or UUID(int=0)

    result = await media_upload_impl(
        pool, redis,
        modality="image",
        session_id=session_uuid,
        file_bytes=file_bytes,
        filename=filename,
        content_type=content_type,
        name=name or "",
        description=description or "",
    )

    return ImageUploadScenarioApiResponse(
        image_id=result.resource_id,
        upload_id=result.upload_id,
    )
