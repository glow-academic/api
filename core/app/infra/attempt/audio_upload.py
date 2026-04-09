"""Attempt audio upload logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for attempt:audio_upload
  3. create_upload — raw file metadata (uploads_entry)
  4. create_audio — audios_entry (length_seconds)
  5. create_audio_upload — link audio <-> upload (audio_uploads_entry)
"""

from __future__ import annotations

import os
import uuid as _uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.media_types import AudioUploadAttemptApiResponse
from app.infra.globals import AUDIO_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audios.create import create_audio
from app.tools.entries.uploads.create import create_upload
from app.utils.cache.invalidate_tags import invalidate_tags


async def audio_upload_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    file_bytes: bytes,
    filename: str,
    content_type: str,
    length_seconds: int = 0,
) -> AudioUploadAttemptApiResponse:
    """Upload an audio file for an attempt.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (attempt:audio_upload)
      3. Write file to disk
      4. create_upload -> uploads_entry
      5. create_audio -> audios_entry
      6. create_audio_upload -> audio_uploads_entry (link)
      7. invalidate_tags
    """
    # -- Step 1: Profile context -----------------------------------------------
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check ----------------------------------------------
    if not has_permission(profile.role_permissions, "attempt", "audio_upload"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload attempt audio.",
        )

    # -- Step 3: Write file to disk --------------------------------------------
    upload_uuid = _uuid.uuid4()

    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".bin"

    relative_path = f"audio/{upload_uuid}{ext}"
    full_path = AUDIO_FOLDER / f"{upload_uuid}{ext}"

    with open(full_path, "wb") as f:
        f.write(file_bytes)

    # -- Step 4-6: DB records in single connection -----------------------------
    session_uuid = session_id or UUID(int=0)

    async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            session_id=session_uuid,
            file_path=relative_path,
            mime_type=content_type,
            size=len(file_bytes),
        )

        audio_result = await create_audio(
            conn,
            session_id=session_uuid,
            length_seconds=length_seconds,
        )

        await create_audio_upload(
            conn,
            audio_id=audio_result.id,
            upload_id=upload_result.id,
            session_id=session_uuid,
        )

    # -- Step 7: Invalidate cache ----------------------------------------------
    await invalidate_tags(["uploads", "entries", "audios"], redis=redis)

    return AudioUploadAttemptApiResponse(
        audio_id=audio_result.id,
        upload_id=upload_result.id,
    )
