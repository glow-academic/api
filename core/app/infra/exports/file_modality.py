"""Canonical file-modality wrapping helper + shared soft/accept plumbing.

Mirrors the 4-step chain in ``app.infra.persona.export``:
  1. upload (file on disk + uploads_entry)
  2. files_resource (the catalog id; this becomes the ``file_id`` returned to the client)
  3. files_entry (junction-linked to the files_resource via file_files_connection)
  4. file_uploads_entry (links files_entry ↔ uploads_entry)
  5. refresh_files_internal (so files_mv resolves the new id immediately)

``wrap_bytes_as_file`` returns a :class:`WrappedFile` carrying every chain id so
the caller can stage them dormant (``soft=True``) and the ack can activate them.

Soft/accept (shared by the bespoke attempt/test/system exports, mirroring the
canonical ``export_persona_impl``):
  * ``soft=True`` creates the whole chain ``active=False`` and records a pending
    soft_call (:func:`stage_export_soft_call`) keyed by the server call_id.
  * the ack (``{idempotency_key, accept}``) flips the chain active or rejects it
    (:func:`accept_staged_export`).
The soft key is the server-minted ``call_id`` (FKs ``calls_entry``), so an
owning tool must exist for ``(artifact, export)`` — otherwise the wrapper writes
no calls_entry and the ledger has nothing to hang off of.
"""

from __future__ import annotations

import os
import uuid as uuid_mod
from datetime import datetime
from typing import NamedTuple
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.globals import UPLOAD_FOLDER
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.mv_refresh_queue import enqueue_pending
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import create_file as create_file_resource
from app.utils.cache.hedged_row import transaction_with_writeback


class WrappedFile(NamedTuple):
    """The full file-modality chain produced by :func:`wrap_bytes_as_file`.

    ``file_id`` (== ``resource_id``) is the catalog id the client downloads by.
    ``entry_id``/``junction_id`` are ``None`` when no ``session_id`` was given
    (the entry + junction steps are session-scoped).
    """

    file_id: UUID
    file_name: str
    upload_id: UUID
    resource_id: UUID
    entry_id: UUID | None
    junction_id: UUID | None


async def wrap_bytes_as_file(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    content: bytes,
    file_name_prefix: str,
    mime_type: str,
    extension: str,
    session_id: UUID | None = None,
    soft: bool = False,
) -> WrappedFile:
    """Persist ``content`` to disk + canonical file chain, return a WrappedFile.

    ``file_name_prefix`` should be like ``"dashboard_export"``; the helper appends
    a timestamp + extension. ``extension`` excludes the leading dot. When
    ``soft=True`` every chain row is created ``active=False`` (dormant) for the
    caller to stage; the MV refresh is skipped (the ack does it).
    """
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"{file_name_prefix}_{timestamp}.{extension}"

    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.{extension}"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(content)

    entry_row = None
    junction_row = None
    async with pool.acquire() as conn:
        upload_row = await create_upload(
            conn,
            redis, session_id=session_id,
            file_path=relative_path,
            mime_type=mime_type,
            size=len(content),
            soft=soft,
        )
        resource_row = await create_file_resource(conn, redis, soft=soft)
        if session_id is not None:
            entry_row = await create_file_entry(
                conn,
                redis,
                session_id=session_id,
                files_id=resource_row.id,
                soft=soft,
            )
            junction_row = await create_file_upload(
                conn,
                redis, file_id=entry_row.id,
                upload_id=upload_row.id,
                session_id=session_id,
                soft=soft,
            )
    # Dormant rows won't surface in files_mv anyway — defer the refresh to the
    # ack (accept_staged_export) so a staged export costs nothing until promoted.
    if session_id is not None and redis is not None and not soft:
        await enqueue_pending(redis, "files_mv")

    return WrappedFile(
        file_id=resource_row.id,
        file_name=file_name,
        upload_id=upload_row.id,
        resource_id=resource_row.id,
        entry_id=entry_row.id if entry_row is not None else None,
        junction_id=junction_row.id if junction_row is not None else None,
    )


async def stage_export_soft_call(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    artifact: str,
    call_id: UUID,
    wrapped: WrappedFile,
    row_count: int,
) -> None:
    """Record a dormant export chain as a pending soft_call (keyed by call_id).

    No-op when the entry/junction steps were skipped (no session_id) — there's
    no full chain to activate later.
    """
    if wrapped.entry_id is None or wrapped.junction_id is None:
        return
    async with pool.acquire() as conn:
        await create_soft_call(
            conn,
            redis,
            call_id=call_id,
            artifact=artifact,
            operation="export",
            artifact_id=wrapped.resource_id,
            status="pending",
            patch={
                "upload_id": str(wrapped.upload_id),
                "resource_id": str(wrapped.resource_id),
                "entry_id": str(wrapped.entry_id),
                "junction_id": str(wrapped.junction_id),
                "file_name": wrapped.file_name,
                "row_count": row_count,
            },
        )


async def accept_staged_export(
    pool: asyncpg.Pool,
    redis: Redis,  # type: ignore[type-arg]
    *,
    artifact: str,
    idempotency_key: UUID,
    accept: bool,
) -> tuple[UUID, str, int]:
    """Ack short-circuit shared by bespoke exports: activate/reject a staged chain.

    Returns ``(file_id, file_name, row_count)`` for the caller's response model.
    """
    async with pool.acquire() as conn:
        entry = await get_soft_call(conn, idempotency_key, redis, artifact=artifact)
    if entry is None or entry.status != "pending" or entry.operation != "export":
        raise HTTPException(status_code=404, detail="No pending export for this call.")
    ids = entry.patch or {}
    if accept:
        async with pool.acquire() as conn:
            async with transaction_with_writeback(conn):
                await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                await activate_rows(conn, table="files_resource", ids=[UUID(ids["resource_id"])])
                await activate_rows(conn, table="files_entry", ids=[UUID(ids["entry_id"])])
                await activate_rows(conn, table="file_uploads_entry", ids=[UUID(ids["junction_id"])])
        await enqueue_pending(redis, "files_mv")
    async with pool.acquire() as conn:
        await create_soft_call(
            conn,
            redis,
            call_id=idempotency_key,
            artifact=artifact,
            operation="export",
            artifact_id=entry.artifact_id,
            status="accepted" if accept else "rejected",
        )
    return entry.artifact_id, str(ids.get("file_name", "")), int(ids.get("row_count", 0))


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
