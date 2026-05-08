"""Model call download logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. has_permission — permission check for model:call_download
  3. search_call_uploads — resolve call_id -> upload_id
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

from app.infra.model.types import CallDownloadModelApiResult
from app.infra.globals import CALL_FOLDER, UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.call_uploads.search import search_call_uploads
from app.tools.entries.uploads.get import get_upload


async def call_download_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    call_id: UUID,
    session_id: UUID | None = None,
) -> CallDownloadModelApiResult:
    """Resolve a call resource to its file on disk."""
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "model", "call_download"):
        raise HTTPException(
            status_code=403,
            detail="You don\'t have permission to download model calls.",
        )

    async with pool.acquire() as conn:
        junctions = await search_call_uploads(conn, call_ids=[call_id], limit=1)

        if not junctions:
            raise HTTPException(
                status_code=404,
                detail="No upload found for this call.",
            )

        upload = await get_upload(conn, junctions[0].upload_id)

    if upload is None:
        raise HTTPException(status_code=404, detail="Upload record not found.")

    file_path = os.path.join(CALL_FOLDER, os.path.basename(upload.file_path))
    if not os.path.exists(file_path):
        file_path = os.path.join(UPLOAD_FOLDER, upload.file_path)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Call file not found on disk.")

    return CallDownloadModelApiResult(
        upload_id=upload.id,
        file_path=file_path,
        content_type=upload.mime_type,
        filename=os.path.basename(upload.file_path),
        size=upload.size,
    )
