"""Create a text linked to an upload from raw content.

Building block: save_text_upload + upload + text_resource + text_entry + text_upload.
Used by document draft infra and seed runner.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.tools.entries.save_text_upload import save_text_upload
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text as create_text_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.texts.create import (
    create_text as create_text_resource,
)


@dataclass(frozen=True)
class CreateDocumentTextResult:
    texts_resource_id: UUID  # link this to document via text_ids
    text_entry_id: UUID
    upload_id: UUID
    text_upload_id: UUID


async def create_document_text(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    content: str,
    session_id: UUID,
    upload_folder: Path,
) -> CreateDocumentTextResult:
    """Create a text from raw content, writing to disk and creating the full entry chain.

    Chain: save_text_upload → create_upload → create_text_resource
         → create_text_entry → create_text_upload.
    """
    # 1. Generate upload ID and write content to disk
    upload_id = uuid.uuid4()
    file_path = save_text_upload(content, upload_id, upload_folder)
    size = (upload_folder / file_path).stat().st_size

    # 2. Create uploads entry
    upload = await create_upload(
        conn,
        session_id=session_id,
        file_path=file_path,
        mime_type="text/plain",
        size=size,
    )

    # 3. Create texts resource
    text_resource = await create_text_resource(conn, redis)

    # 4. Create texts entry linked to resource
    text_entry = await create_text_entry(
        conn,
        session_id=session_id,
        texts_id=text_resource.id,
    )

    # 5. Link text entry ↔ upload entry
    text_upload = await create_text_upload(
        conn,
        text_id=text_entry.id,
        upload_id=upload.id,
        session_id=session_id,
    )

    return CreateDocumentTextResult(
        texts_resource_id=text_resource.id,
        text_entry_id=text_entry.id,
        upload_id=upload.id,
        text_upload_id=text_upload.id,
    )
