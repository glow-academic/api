"""Canonical media upload chain.

Produces the full reference chain from raw bytes (or an existing upload):

  uploads_entry
    └─ <m>s_resource           (create_<m>_resource)
    └─ <m>s_entry              (create_<m> with <m>s_id kwarg — the entry
       └─ <m>s_<m>s_connection  tool writes the junction inline)
    └─ <m>_uploads_entry       (create_<m>_upload — entry ↔ upload link)

Callers:
  * app/infra/websocket/adapters/media/litellm.py._save_media  (generate)
  * app/infra/attempt/audio_upload.py                          (user audio upload)
  * app/infra/scenario/image_upload.py                         (user image upload)

No permission checks here. Authorization lives at the artifact boundary —
you don't reach this function unless the caller already decided you may.
"""

from __future__ import annotations

import os
import uuid as _uuid
from pathlib import Path
from uuid import UUID

import asyncpg
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.globals import AUDIO_FOLDER, IMAGE_FOLDER, VIDEO_FOLDER
from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audios.create import create_audio
from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from app.tools.entries.video_uploads.create import create_video_upload
from app.tools.entries.videos.create import create_video
from app.tools.resources.audios.create import create_audio_resource
from app.tools.resources.images.create import create_image as create_image_resource
from app.tools.resources.videos.create import create_video as create_video_resource
from app.utils.cache.invalidate_tags import invalidate_tags


_FOLDERS: dict[str, Path] = {
    "audio": AUDIO_FOLDER,
    "image": IMAGE_FOLDER,
    "video": VIDEO_FOLDER,
}


class MediaUploadResult(BaseModel):
    upload_id: UUID
    entry_id: UUID
    resource_id: UUID
    file_path: str
    mime_type: str
    file_size: int


async def media_upload_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    modality: str,
    session_id: UUID,
    file_bytes: bytes | None = None,
    upload_id: UUID | None = None,
    filename: str = "",
    content_type: str = "",
    length_seconds: int = 0,
    name: str = "",
    description: str = "",
) -> MediaUploadResult:
    """Run the full uploads → resource → entry → link chain for one modality.

    Two entry modes:
      * ``file_bytes`` — write bytes to the modality folder and create the
        ``uploads_entry`` here.
      * ``upload_id`` — reuse an existing upload (e.g. promote realtime
        capture) and only build the resource/entry/link on top.
    """
    if modality not in _FOLDERS:
        raise ValueError(f"Unsupported media modality: {modality}")
    if file_bytes is None and upload_id is None:
        raise ValueError("media_upload_impl requires either file_bytes or upload_id")

    folder = _FOLDERS[modality]
    resource_name = name or f"{modality}-{_uuid.uuid4()}"
    resource_description = description

    async with pool.acquire() as conn:
        if upload_id is None:
            assert file_bytes is not None
            upload_uuid = _uuid.uuid4()
            _, ext = os.path.splitext(filename)
            if not ext:
                ext = ".bin"
            relative_path = f"{modality}/{upload_uuid}{ext}"
            full_path = folder / f"{upload_uuid}{ext}"
            folder.mkdir(parents=True, exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(file_bytes)
            file_size = len(file_bytes)
            mime_type = content_type or "application/octet-stream"
            upload_row = await create_upload(
                conn,
                session_id=session_id,
                file_path=relative_path,
                mime_type=mime_type,
                size=file_size,
            )
            upload_id = upload_row.id
        else:
            existing = await get_upload(conn, upload_id)
            if existing is None:
                raise ValueError(f"Upload {upload_id} not found")
            relative_path = existing.file_path
            mime_type = existing.mime_type
            file_size = existing.size

        if modality == "audio":
            resource = await create_audio_resource(
                conn,
                name=resource_name,
                description=resource_description,
                redis=redis,
            )
            entry = await create_audio(
                conn,
                session_id=session_id,
                audios_id=resource.id,
                length_seconds=length_seconds,
            )
            await create_audio_upload(
                conn,
                audio_id=entry.id,
                upload_id=upload_id,
                session_id=session_id,
            )
        elif modality == "image":
            resource = await create_image_resource(
                conn,
                name=resource_name,
                description=resource_description,
                redis=redis,
            )
            entry = await create_image(
                conn,
                session_id=session_id,
                images_id=resource.id,
            )
            await create_image_upload(
                conn,
                image_id=entry.id,
                upload_id=upload_id,
                session_id=session_id,
            )
        else:
            resource = await create_video_resource(
                conn,
                name=resource_name,
                description=resource_description,
                redis=redis,
            )
            entry = await create_video(
                conn,
                session_id=session_id,
                videos_id=resource.id,
                length_seconds=length_seconds,
            )
            await create_video_upload(
                conn,
                video_id=entry.id,
                upload_id=upload_id,
                session_id=session_id,
            )

    await invalidate_tags(
        ["uploads", "entries", f"{modality}s", "resources"], redis=redis,
    )

    return MediaUploadResult(
        upload_id=upload_id,
        entry_id=entry.id,
        resource_id=resource.id,
        file_path=relative_path,
        mime_type=mime_type,
        file_size=file_size,
    )
