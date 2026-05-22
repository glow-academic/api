"""Attempt audio upload — permission + canonical media chain.

Thin wrapper around ``media_upload_impl``:
  1. resolve_profile_identity_context
  2. has_permission("attempt", "audio_upload")
  3. media_upload_impl(modality="audio", ...)

Two entry modes (delegated to the shared core):
  * ``file_bytes`` — new upload bytes, writes the file + uploads_entry.
  * ``upload_id``  — promote an existing upload (e.g. realtime capture).

Soft/accept follows the canonical CRUD lifecycle (see document/file_upload):
  - ``soft=True`` → stage the whole chain dormant + a pending ``soft_calls_entry``.
  - ``{idempotency_key, accept}`` → promote (``activate_rows`` per row) or reject.

Returns ``{audio_id, audios_id, upload_id}``.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.attempt.media_types import AudioUploadAttemptApiResponse
from app.infra.media.upload import media_upload_impl
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call

ARTIFACT = "attempt"
OPERATION = "audio_upload"


async def audio_upload_attempt_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    upload_id: UUID | None = None,
    file_bytes: bytes | None = None,
    filename: str = "",
    content_type: str = "audio/webm",
    length_seconds: int = 0,
    name: str = "",
    description: str = "",
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> AudioUploadAttemptApiResponse:
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    if not has_permission(profile.role_permissions, "attempt", "audio_upload"):
        raise HTTPException(
            status_code=403,
            detail="You don't have permission to upload attempt audio.",
        )

    # ── Short-circuit: ack path (mirrors document/file_upload) ─────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending audio upload for this call.",
            )
        ids = entry.patch or {}

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="audios_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="audios_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="audio_uploads_entry", ids=[UUID(ids["junction_id"])])
        # accept=False: dormant rows stay inactive; the 'rejected' ledger row is canonical.

        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=idempotency_key,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )

        return AudioUploadAttemptApiResponse(
            audio_id=UUID(ids["entry_id"]),
            audios_id=entry.artifact_id,
            upload_id=UUID(ids["upload_id"]),
            idempotency_key=idempotency_key,
        )

    if upload_id is None and not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Either upload_id (promote existing) or file_bytes (new upload) is required.",
        )

    session_uuid = session_id or profile.session_id or UUID(int=0)

    with timed("media_upload"):
        result = await media_upload_impl(
            pool, redis,
            modality="audio",
            session_id=session_uuid,
            file_bytes=file_bytes,
            upload_id=upload_id,
            filename=filename,
            content_type=content_type,
            soft=soft,
            length_seconds=length_seconds,
            name=name,
            description=description,
        )

    if soft and call_id is not None:
        async with pool.acquire() as conn:
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=result.resource_id,
                status="pending",
                patch={
                    "upload_id": str(result.upload_id),
                    "resource_id": str(result.resource_id),
                    "entry_id": str(result.entry_id),
                    "junction_id": str(result.junction_id),
                },
            )

    return AudioUploadAttemptApiResponse(
        audio_id=result.entry_id,
        audios_id=result.resource_id,
        upload_id=result.upload_id,
        idempotency_key=call_id,
    )
