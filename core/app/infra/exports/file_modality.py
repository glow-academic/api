"""Canonical file-modality wrapping helper.

Mirrors the 4-step chain in ``app.infra.persona.export``:
  1. upload (file on disk + uploads_entry)
  2. files_resource (the catalog id; this becomes the ``file_id`` returned to the client)
  3. files_entry (junction-linked to the files_resource via file_files_connection)
  4. file_uploads_entry (links files_entry ↔ uploads_entry)
  5. refresh_files_internal (so files_mv resolves the new id immediately)

Returns ``(file_id, file_name)``. The caller stamps row_count.
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.files.refresh import refresh_files_internal
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import create_file as create_file_resource


async def wrap_bytes_as_file(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    content: bytes,
    file_name_prefix: str,
    mime_type: str,
    extension: str,
    session_id: UUID | None = None,
) -> tuple[UUID, str]:
    """Persist ``content`` to disk + canonical file chain, return (file_id, file_name).

    ``file_name_prefix`` should be like ``"dashboard_export"``; the helper appends
    a timestamp + extension. ``extension`` excludes the leading dot.
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"{file_name_prefix}_{timestamp}.{extension}"

    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.{extension}"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(content)

    async with pool.acquire() as conn:
        upload_row = await create_upload(
            conn,
            redis, session_id=session_id,
            file_path=relative_path,
            mime_type=mime_type,
            size=len(content),
        )
        resource_row = await create_file_resource(conn, redis)
        if session_id is not None:
            entry_row = await create_file_entry(
                conn,
                session_id=session_id,
                files_id=resource_row.id,
            )
            await create_file_upload(
                conn,
                redis, file_id=entry_row.id,
                upload_id=upload_row.id,
                session_id=session_id,
            )
            await refresh_files_internal(conn, redis)

    return resource_row.id, file_name


def extension_from_mime(mime_type: str) -> str:
    """Pick a reasonable filename extension for a known MIME type."""
    mapping = {
        "application/zip": "zip",
        "text/csv": "csv",
        "application/json": "json",
        "application/pdf": "pdf",
        "text/plain": "txt",
    }
    return mapping.get(mime_type, "bin")
