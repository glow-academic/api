"""Create a video linked to an upload from a file on disk.

Building block: create_upload + video_resource + video_entry + video_upload.
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

from app.tools.entries.uploads.create import create_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.videos.create import create_video as create_video_entry
from app.tools.resources.videos.create import (
    create_video as create_video_resource,
)


@dataclass(frozen=True)
class CreateScenarioVideoResult:
    videos_resource_id: UUID
    video_entry_id: UUID
    upload_id: UUID
    video_upload_id: UUID


async def create_scenario_video(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    source_path: Path,
    mime_type: str,
    session_id: UUID,
    upload_folder: Path,
    videos_resource_id: UUID | None = None,
    name: str = "",
    description: str = "",
    length_seconds: int = 0,
) -> CreateScenarioVideoResult:
    """Create a video from a source file, copying to upload folder and creating the full entry chain.

    Chain: copy file → create_upload → create_video_resource
         → create_video_entry → create_video_upload.
    """
    # 1. Copy source file to upload folder
    dest_name = f"video/{uuid.uuid4()}{source_path.suffix}"
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

    # 3. Create videos resource
    video_resource = await create_video_resource(
        conn, name=name, description=description, redis=redis, id=videos_resource_id,
    )

    # 4. Create videos entry linked to resource
    video_entry = await create_video_entry(
        conn,
        redis,
        session_id=session_id,
        videos_id=video_resource.id,
        length_seconds=length_seconds,
    )

    # 5. Link video entry ↔ upload entry
    video_upload = await create_video_upload(
        conn,
        redis, video_id=video_entry.id,
        upload_id=upload.id,
        session_id=session_id,
    )

    return CreateScenarioVideoResult(
        videos_resource_id=video_resource.id,
        video_entry_id=video_entry.id,
        upload_id=upload.id,
        video_upload_id=video_upload.id,
    )
