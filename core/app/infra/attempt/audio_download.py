"""Attempt audio download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for attempt:audio_download
  3. Either ``search_audio_uploads`` (entry-id) or ``get_upload_by_audios_id``
     (resource-id) — the caller's ``audio_id`` may be either, depending on
     whether it came from the assistant realtime path (entry id) or a
     user-message attachment (resource id surfaced by the chat MV via
     ``attempt_audio_entry.audios_id``).
  4. ``get_upload`` — resolve upload_id -> file_path, mime_type, size.

Returns resolved file metadata. The transport layer (HTTP route / WS input)
decides how to serve it (streaming response vs base64).
"""

from __future__ import annotations

import os
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.media_types import AudioDownloadAttemptApiResult
from app.infra.globals import AUDIO_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.audio_uploads.search import search_audio_uploads
from app.tools.entries.uploads.get import get_upload
from app.tools.resources.audios.get import get_upload_by_audios_id


async def audio_download_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    audio_id: UUID,
    session_id: UUID | None = None,
) -> AudioDownloadAttemptApiResult:
    """Resolve an audio id to its file on disk.

    ``audio_id`` accepts either:
      - ``audios_entry.id`` — canonical for the realtime adapter's
        assistant-audio path (records the entry id directly).
      - ``audios_resource.id`` — what user-message attachments carry
        via ``attempt_audio_entry.audios_id`` and what the chat MV
        surfaces to the FE for playback URLs.

    Flow:
      1. resolve_profile_identity_context -> role, permissions
      2. has_permission check (attempt:audio_download)
      3. Try entry-id path: search_audio_uploads + get_upload
      4. Fall back to resource-id path: get_upload_by_audios_id
      5. Verify file exists on disk
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
    if not has_permission(profile.role_permissions, "attempt", "audio_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download attempt audio.",
        )

    # -- Step 3: Resolve id -> upload ------------------------------------------
    # The caller may pass either an ``audios_entry`` id (the canonical
    # download key) or an ``audios_resource`` id (what
    # ``attempt_audio_entry.audios_id`` and the chat MV surface on user
    # messages). Try entry-id lookup first; on miss, fall back to the
    # canonical resource→upload helper. Both paths land on the same
    # ``uploads_entry`` so the file-fetch downstream is uniform.
    async with pool.acquire() as conn:
        junctions = await search_audio_uploads(conn, redis, audio_ids=[audio_id], limit=1)
        upload = None
        if junctions:
            upload = await get_upload(conn, junctions[0].upload_id, redis)
        else:
            # Resource-id path. ``get_upload_by_audios_id`` walks
            # ``audios_resource → audios_audios_connection → audios_entry
            # → audio_uploads_entry → uploads_entry`` in one helper.
            upload = await get_upload_by_audios_id(conn, audio_id)

    if upload is None:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this audio.",
        )

    # -- Step 5: Verify file on disk -------------------------------------------
    file_path = os.path.join(AUDIO_FOLDER, os.path.basename(upload.file_path))

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Audio file not found on disk.")

    return AudioDownloadAttemptApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
    )
