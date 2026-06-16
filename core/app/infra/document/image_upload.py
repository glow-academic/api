"""Document image upload — permission + canonical media chain.

Mirror of ``app.infra.scenario.image_upload`` — see that file for the
canonical rationale. Only difference is the artifact name + permission
namespace so audit events stamp ``document.image_upload.*`` and the
permission check goes through ``document:image_upload``.
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
from app.infra.document.types import ImageUploadDocumentApiResponse
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.utils.cache.hedged_row import transaction_with_writeback

ARTIFACT = "document"
OPERATION = "image_upload"


async def image_upload_document_impl(
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
) -> ImageUploadDocumentApiResponse:
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    with timed("permissions"):
        if not has_permission(profile.role_permissions, "document", "image_upload"):
            raise HTTPException(
                status_code=403,
                detail="You don't have permission to upload document images.",
            )

    # ── Ack short-circuit ───────────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending image upload for this call.",
            )
        ids = entry.patch or {}

        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="images_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="images_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="image_uploads_entry", ids=[UUID(ids["junction_id"])])

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

        return ImageUploadDocumentApiResponse(
            image_id=entry.artifact_id,
            upload_id=UUID(ids["upload_id"]),
            idempotency_key=idempotency_key,
        )

    # ── First-call requirements ─────────────────────────────────────
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
            modality="image",
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

    return ImageUploadDocumentApiResponse(
        image_id=result.resource_id,
        upload_id=result.upload_id,
        idempotency_key=call_id,
    )
