"""Scenario video upload — permission + canonical media chain.

Thin wrapper around ``media_upload_impl`` (now shares the canonical chain with
scenario/image_upload and attempt/audio_upload):
  1. resolve_profile_identity_context
  2. has_permission("scenario", "video_upload")
  3. media_upload_impl(modality="video", ...)

Soft/accept follows the canonical CRUD lifecycle (see document/file_upload):
  - ``soft=True`` → stage the whole chain dormant + a pending ``soft_calls_entry``.
  - ``{idempotency_key, accept}`` → promote (``activate_rows`` per row) or reject.

Does NOT link the video to any scenario — that is a separate update operation.
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.media.upload import media_upload_impl
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.scenario.types import VideoUploadScenarioApiResponse
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "scenario"
OPERATION = "video_upload"


async def video_upload_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    name: str | None = None,
    description: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> VideoUploadScenarioApiResponse:
    """Upload a video for later use in scenarios (canonical chain + soft/accept)."""
    # -- Step 1: Profile context ------------------------------------------------
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Permission check -----------------------------------------------
    with timed("permissions"):
        if not has_permission(profile.role_permissions, "scenario", "video_upload"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to upload scenario videos.",
            )

    # ── Short-circuit: ack path (mirrors document/file_upload) ─────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending video upload for this call.",
            )
        ids = entry.patch or {}

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="videos_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="videos_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="video_uploads_entry", ids=[UUID(ids["junction_id"])])
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

        return VideoUploadScenarioApiResponse(
            video_id=entry.artifact_id,
            upload_id=UUID(ids["upload_id"]),
            idempotency_key=idempotency_key,
        )

    # ── First-call requirements ────────────────────────────────────────────────
    if file_bytes is None or not filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required for upload (or pass `idempotency_key` + "
            "`accept` for the ack call).",
        )

    session_uuid = session_id or profile.session_id or UUID(int=0)

    with timed("media_decode"):
        result = await media_upload_impl(
            pool, redis,
            modality="video",
            session_id=session_uuid,
            file_bytes=file_bytes,
            filename=filename,
            content_type=content_type or "",
            soft=soft,
            name=name or "",
            description=description or "",
        )

    if soft and call_id is not None:
      with timed("db_insert"):
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

    return VideoUploadScenarioApiResponse(
        video_id=result.resource_id,
        upload_id=result.upload_id,
        idempotency_key=call_id,
    )
