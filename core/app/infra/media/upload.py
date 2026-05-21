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

from app.infra.globals import AUDIO_FOLDER, IMAGE_FOLDER, UPLOAD_FOLDER, VIDEO_FOLDER
from app.infra.tools.entries.create_run_message import create_run_message
from app.infra.tools.entries.save_text_upload import save_text_upload
from app.tools.entries.audio_uploads.create import create_audio_upload
from app.tools.entries.audios.create import create_audio
from app.tools.entries.image_uploads.create import create_image_upload
from app.tools.entries.images.create import create_image
from app.tools.entries.message_uploads.create import create_message_upload
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


_MODALITY_TABLE: dict[str, str] = {
    "audio": "audios_resource",
    "image": "images_resource",
    "video": "videos_resource",
}


async def _resolve_unique_resource_name(
    pool: asyncpg.Pool, *, modality: str, base_name: str,
) -> str:
    """Return ``base_name`` if no active resource of that name exists,
    else the smallest ``f"{base_name} {n}"`` (n=1,2,3,…) that is free.

    Scoped globally across the modality's resource table. Callers that
    want per-user scoping can layer it on later — keeping the SQL flat
    avoids leaking session context into the upload chain.
    """
    table = _MODALITY_TABLE.get(modality)
    if not table:
        return base_name
    async with pool.acquire() as conn:
        # Pull every active row whose name matches the base OR has a
        # ``base N`` suffix. SQL ``LIKE`` with a single round trip is
        # cheaper than a loop probing for each suffix.
        rows = await conn.fetch(
            f"SELECT name FROM {table} "
            f"WHERE active = true AND (name = $1 OR name LIKE $2)",
            base_name, f"{base_name} %",
        )
    taken: set[str] = {r["name"] for r in rows}
    if base_name not in taken:
        return base_name
    n = 1
    while f"{base_name} {n}" in taken:
        n += 1
    return f"{base_name} {n}"


class MediaUploadResult(BaseModel):
    upload_id: UUID
    entry_id: UUID
    resource_id: UUID
    file_path: str
    mime_type: str
    file_size: int
    # ``messages_entry.id`` of the assistant message this upload was
    # attributed to (the announcement row). ``None`` when no run/
    # ``attribute_to_run`` was provided (e.g. manual user uploads).
    # The adapter forwards this onto the media-complete event so the
    # FE listener's pre-rendered skeleton (keyed by message_id from
    # ``image.start``) can locate itself and swap in the real ``<img>``.
    message_id: UUID | None = None


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
    run_id: UUID | None = None,
    attribute_to_run: bool = False,
    message_id: UUID | None = None,
) -> MediaUploadResult:
    """Run the full uploads → resource → entry → link chain for one modality.

    Two entry modes:
      * ``file_bytes`` — write bytes to the modality folder and create the
        ``uploads_entry`` here.
      * ``upload_id`` — reuse an existing upload (e.g. promote realtime
        capture) and only build the resource/entry/link on top.

    Run attribution (optional, opt-in via ``attribute_to_run=True``):
      When the caller is a media-dispatch path that has a ``run_id`` in
      hand, this also writes the canonical ``run_id → message → upload``
      bridge:
        * an assistant ``messages_entry`` summarizing the produced asset
        * a ``text_uploads_entry`` for the message body (one-line summary)
        * a ``message_uploads_entry`` linking the message to the produced
          modality upload (the image/video/audio blob)
      This matches the junction shape that ``create_tool_call`` writes for
      agentic tool-produced uploads, so downstream consumers (chat MVs,
      ``_watch.snapshot``, future "what did this run make?" queries) see a
      uniform link regardless of which path produced the upload.

      Manual user-upload routes (``scenario/image_upload``,
      ``attempt/audio_upload``) leave ``attribute_to_run=False`` because
      no run produced them. Tool-call paths also leave it ``False`` — the
      audit-side ``create_tool_call`` writes the junction itself after
      this returns, and double-writing would create duplicate messages.
    """
    if modality not in _FOLDERS:
        raise ValueError(f"Unsupported media modality: {modality}")
    if file_bytes is None and upload_id is None:
        raise ValueError("media_upload_impl requires either file_bytes or upload_id")

    folder = _FOLDERS[modality]
    # Honor caller-supplied label; only fall back to the UUID-based
    # placeholder when nothing was provided (LLM omitted the ``title``
    # arg AND no filename-derived name flowed in). When the bare name
    # already exists, append " 1", " 2", … so multiple generations
    # under the same title still get distinct rows. The original keeps
    # the bare title so the first one stays clean.
    resource_name = name or f"{modality}-{_uuid.uuid4()}"
    if name:
        resource_name = await _resolve_unique_resource_name(
            pool, modality=modality, base_name=name,
        )
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
                redis, session_id=session_id,
                file_path=relative_path,
                mime_type=mime_type,
                size=file_size,
            )
            upload_id = upload_row.id
        else:
            existing = await get_upload(conn, upload_id, redis)
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
                redis, session_id=session_id,
                audios_id=resource.id,
                length_seconds=length_seconds,
            )
            await create_audio_upload(
                conn,
                redis, audio_id=entry.id,
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
                redis, session_id=session_id,
                images_id=resource.id,
            )
            await create_image_upload(
                conn,
                redis, image_id=entry.id,
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
                redis, session_id=session_id,
                videos_id=resource.id,
                length_seconds=length_seconds,
            )
            await create_video_upload(
                conn,
                redis, video_id=entry.id,
                upload_id=upload_id,
                session_id=session_id,
            )

        # Initialize before the conditional so the return-shape path
        # always has a value, even when no message gets created (manual
        # upload, no run_id).
        attributed_message_id: UUID | None = None

        # ── Optional: wire the run_id → message → upload junction so
        # downstream "what did this run produce" queries can walk the
        # canonical messages_entry / message_uploads_entry path. Same
        # shape as create_tool_call's audit-side write; mutually
        # exclusive with that path (only ONE writer per upload).
        if run_id is not None and attribute_to_run:
            summary = (
                f"Generated {modality} resource: {resource_name}"
                if not resource_description
                else f"Generated {modality}: {resource_description}"
            )
            text_upload_uuid = _uuid.uuid4()
            text_rel_path = save_text_upload(
                summary, text_upload_uuid, UPLOAD_FOLDER,
            )
            text_size = (UPLOAD_FOLDER / text_rel_path).stat().st_size
            text_upload = await create_upload(
                conn,
                redis, session_id=session_id,
                file_path=text_rel_path,
                mime_type="text/plain",
                size=text_size,
            )
            msg = await create_run_message(
                conn,
                redis,
                run_id=run_id,
                session_id=session_id,
                role="assistant",
                upload_id=text_upload.id,
                # Caller pre-minted this so the FE's optimistic skeleton
                # bubble (created on ``image.start`` keyed by this id)
                # shares the same id as the persisted row. ``None`` falls
                # back to ``uuidv7()`` on the underlying ``create_message``.
                id=message_id,
            )
            await create_message_upload(
                conn,
                redis, message_id=msg.message_id,
                upload_id=upload_id,
                session_id=session_id,
            )
            # Capture the resolved id (either the caller's pre-mint, or
            # the fresh uuidv7 the INSERT generated) for the response.
            attributed_message_id = msg.message_id

    await invalidate_tags(
        ["uploads", "entries", f"{modality}s", "resources"], redis=redis,
    )

    # Synchronously refresh the modality MV before returning. The FE
    # picks up the ``.complete`` SSE event the moment ``_save_media``
    # returns and immediately fires ``/scenario/image_download`` (which
    # reads from ``images_mv``). Without a blocking refresh here the
    # scheduler's next tick (~1–2s) loses the race: the FE's first
    # download hits a stale MV and 404s.
    #
    # ``REFRESH MATERIALIZED VIEW CONCURRENTLY`` is ~50–200ms for these
    # MVs and is the established pattern (the per-modality
    # ``refresh_*_internal`` primitives are the same ones the async
    # scheduler invokes). For the run-attribution case, also refresh
    # ``messages_mv`` so a subsequent ``/scenario/group`` refetch sees
    # the new attachment on the assistant message.
    try:
        async with pool.acquire() as conn:
            if modality == "image":
                from app.tools.entries.images.refresh import refresh_images_internal
                await refresh_images_internal(conn, redis)
            elif modality == "video":
                from app.tools.entries.videos.refresh import refresh_videos_internal
                await refresh_videos_internal(conn, redis)
            elif modality == "audio":
                from app.tools.entries.audios.refresh import refresh_audios_internal
                await refresh_audios_internal(conn, redis)
            if run_id is not None and attribute_to_run:
                from app.tools.entries.messages.refresh import (
                    refresh_messages_internal,
                )
                await refresh_messages_internal(conn, redis)
    except Exception:
        # Never break the upload chain on a refresh hiccup — the
        # underlying rows are committed, the FE may just see a brief
        # 404 until the async scheduler's next tick recovers the MV.
        pass

    return MediaUploadResult(
        upload_id=upload_id,
        entry_id=entry.id,
        resource_id=resource.id,
        file_path=relative_path,
        mime_type=mime_type,
        file_size=file_size,
        message_id=attributed_message_id,
    )
