"""Test file download logic — composable infra architecture.

Mirrors ``app.infra.persona.file_download``:
  1. resolve_profile_identity_context → profile (role, permissions)
  2. has_permission check for ``test:file_download``
  3. search_files(files_ids=[file_id]) → file_path, mime_type, size
  4. Verify file exists on disk
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
from app.infra.test.media_types import FileDownloadTestApiResult
from app.tools.entries.files.search import search_files


async def file_download_test_impl(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    profile_id: UUID,
    file_id: UUID,
    session_id: UUID | None = None,
) -> FileDownloadTestApiResult:
    """Resolve a file resource to its file on disk for the test artifact."""
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "test", "file_download"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to download test files.",
        )

    async with pool.acquire() as conn:
        results = await search_files(conn, files_ids=[file_id], limit=1)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No upload found for this file.",
        )

    file_record = results[0]
    file_path = os.path.join(UPLOAD_FOLDER, file_record.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileDownloadTestApiResult(
        upload_id=file_record.upload_id,
        file_path=file_path,
        content_type=file_record.mime_type,
        filename=os.path.basename(file_record.file_path),
        size=file_record.size,
    )
