"""Create an image linked to an upload from a file on disk.

Building block: create_upload + image_resource + image_entry + image_upload.
Used by seed runner.
"""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image as create_image_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.images.create import (
    create_image as create_image_resource,
)


@dataclass(frozen=True)
class CreateDocumentImageResult:
    images_resource_id: UUID
    image_entry_id: UUID
    upload_id: UUID
    image_upload_id: UUID


async def create_document_image(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    source_path: Path,
    mime_type: str,
    session_id: UUID,
    upload_folder: Path,
    images_resource_id: UUID | None = None,
    name: str = "",
    description: str = "",
) -> CreateDocumentImageResult:
    """Create an image from a source file, copying to upload folder and creating the full entry chain.

    Chain: copy file → create_upload → create_image_resource
         → create_image_entry → create_image_upload.
    """
    # 1. Copy source file to upload folder
    dest_name = f"image/{uuid.uuid4()}{source_path.suffix}"
    dest_path = upload_folder / dest_name
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, dest_path)
    size = dest_path.stat().st_size

    # 2. Create uploads entry
    upload = await create_upload(
        conn,
        redis, session_id=session_id,
        file_path=dest_name,
        mime_type=mime_type,
        size=size,
    )

    # 3. Create images resource
    image_resource = await create_image_resource(
        conn, name=name, description=description, redis=redis, id=images_resource_id,
    )

    # 4. Create images entry linked to resource
    image_entry = await create_image_entry(
        conn,
        session_id=session_id,
        images_id=image_resource.id,
    )

    # 5. Link image entry ↔ upload entry
    image_upload = await create_image_upload(
        conn,
        redis, image_id=image_entry.id,
        upload_id=upload.id,
        session_id=session_id,
    )

    return CreateDocumentImageResult(
        images_resource_id=image_resource.id,
        image_entry_id=image_entry.id,
        upload_id=upload.id,
        image_upload_id=image_upload.id,
    )
