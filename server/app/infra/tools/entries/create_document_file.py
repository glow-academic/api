"""Create a file linked to an upload from a file on disk.

Building block: create_upload + file_resource + file_entry + file_upload.
Used by document draft infra and seed runner.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import (
    create_file as create_file_resource,
)


@dataclass(frozen=True)
class CreateDocumentFileResult:
    files_resource_id: UUID  # link this to document via file_ids
    file_entry_id: UUID
    upload_id: UUID
    file_upload_id: UUID


async def create_document_file(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    source_path: Path,
    mime_type: str,
    session_id: UUID,
    upload_folder: Path,
) -> CreateDocumentFileResult:
    """Create a file from a source file, copying to upload folder and creating the full entry chain.

    Chain: copy file → create_upload → create_file_resource
         → create_file_entry → create_file_upload.
    """
    # 1. Copy source file to upload folder
    dest_name = f"{uuid.uuid4()}{source_path.suffix}"
    dest_path = upload_folder / dest_name
    shutil.copy2(source_path, dest_path)
    size = dest_path.stat().st_size

    # 2. Create uploads entry
    upload = await create_upload(
        conn,
        session_id=session_id,
        file_path=dest_name,
        mime_type=mime_type,
        size=size,
    )

    # 3. Create files resource
    file_resource = await create_file_resource(conn, redis)

    # 4. Create files entry linked to resource
    file_entry = await create_file_entry(
        conn,
        session_id=session_id,
        files_id=file_resource.id,
    )

    # 5. Link file entry ↔ upload entry
    file_upload = await create_file_upload(
        conn,
        file_id=file_entry.id,
        upload_id=upload.id,
        session_id=session_id,
    )

    return CreateDocumentFileResult(
        files_resource_id=file_resource.id,
        file_entry_id=file_entry.id,
        upload_id=upload.id,
        file_upload_id=file_upload.id,
    )
