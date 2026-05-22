"""Document text upload logic — composable infra architecture.

Canonical upload chain (mirrors document/file_upload + media_upload_impl):

  uploads_entry
    └─ texts_resource        (create_text_resource)
    └─ texts_entry           (create_text_entry, texts_id=resource.id — writes
       └─ texts_texts_connection  the resource↔entry link inline)
    └─ text_uploads_entry    (create_text_upload, text_id = ENTRY id)

``text_uploads_entry.text_id`` FKs ``texts_entry`` — so the junction must use the
ENTRY id, not the resource id. (The previous impl created only a texts_resource and
handed its id to the junction, which violated the FK on every upload — same bug as
file_upload.)

Soft/accept (canonical CRUD lifecycle): ``soft=True`` stages the whole chain
dormant (``active=False``) + a pending ``soft_calls_entry`` keyed by the audit
wrapper's server ``call_id`` (which FKs ``calls_entry``); the response echoes that
key. The ack ``{idempotency_key, accept}`` promotes (``activate_rows``) or rejects.

Does NOT link the text to any document — that is a separate update operation.
"""

from __future__ import annotations

import os
import uuid as _uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.document.types import TextUploadDocumentApiResponse
from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text as create_text_entry
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.texts.create import create_text as create_text_resource
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "document"
OPERATION = "text_upload"

ALLOWED_TEXT_TYPES = {
    "text/plain",
    "text/html",
    "text/csv",
    "text/markdown",
    "text/xml",
    "application/json",
    "application/xml",
}


async def text_upload_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    file_bytes: bytes | None = None,
    filename: str | None = None,
    content_type: str | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> TextUploadDocumentApiResponse:
    """Upload a text file for later use in documents (canonical chain + soft/accept).

    Soft-call key: ``soft_calls_entry.call_id`` FKs ``calls_entry``, so the pending
    row is keyed by the audit wrapper's server-minted ``call_id`` (not a client
    key); we echo it in the response and the ack arrives with ``idempotency_key``
    set to it.
    """
    # -- Profile context + permission (always) ----------------------------------
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again.",
        )
    with timed("permissions"):
        if not has_permission(profile.role_permissions, "document", "text_upload"):
            raise HTTPException(
                status_code=403, detail="You don't have permission to upload document texts.",
            )

    # ── Short-circuit: ack path (mirrors persona/create) ───────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending text upload for this call.",
            )
        ids = entry.patch or {}

        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="texts_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="texts_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="text_uploads_entry", ids=[UUID(ids["junction_id"])])
        # accept=False: dormant rows stay inactive; the 'rejected' ledger row below
        # is the canonical record.

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

        await invalidate_tags(["uploads", "resources", "texts"], redis=redis)
        return TextUploadDocumentApiResponse(
            text_id=entry.artifact_id,
            upload_id=UUID(ids["upload_id"]),
            idempotency_key=idempotency_key,
        )

    # ── First-call requirements ───────────────────────────────────────────────
    if file_bytes is None or not filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required for upload (or pass `idempotency_key` + "
            "`accept` for the ack call).",
        )
    if content_type not in ALLOWED_TEXT_TYPES:
        raise HTTPException(
            status_code=400, detail=f"Unsupported text type: {content_type}",
        )

    # -- Write file to disk -----------------------------------------------------
    with timed("disk_write"):
        upload_uuid = _uuid.uuid4()
        _, ext = os.path.splitext(filename)
        if not ext:
            ext = ".txt"
        file_path = f"{upload_uuid}{ext}"
        full_path = UPLOAD_FOLDER / f"{upload_uuid}{ext}"
        with open(full_path, "wb") as f:
            f.write(file_bytes)

    # -- Create the canonical chain (dormant when soft) -------------------------
    session_uuid = session_id or UUID(int=0)
    with timed("db_write"):
     async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            redis, session_id=session_uuid,
            file_path=file_path,
            mime_type=content_type,
            size=len(file_bytes),
            soft=soft,
        )
        resource = await create_text_resource(conn, redis, soft=soft)
        # The entry FKs the junction; it links back to the resource inline.
        text_entry = await create_text_entry(
            conn,
            redis, session_id=session_uuid,
            texts_id=resource.id,
            soft=soft,
        )
        junction = await create_text_upload(
            conn,
            redis, text_id=text_entry.id,
            upload_id=upload_result.id,
            session_id=session_uuid,
            soft=soft,
        )
        if soft and call_id is not None:
            await create_soft_call(
                conn,
                redis,
                call_id=call_id,
                artifact=ARTIFACT,
                operation=OPERATION,
                artifact_id=resource.id,
                status="pending",
                patch={
                    "upload_id": str(upload_result.id),
                    "resource_id": str(resource.id),
                    "entry_id": str(text_entry.id),
                    "junction_id": str(junction.id),
                },
            )

    # -- Invalidate cache -------------------------------------------------------
    with timed("invalidate"):
        await invalidate_tags(["uploads", "resources", "texts"], redis=redis)

    return TextUploadDocumentApiResponse(
        text_id=resource.id,
        upload_id=upload_result.id,
        idempotency_key=call_id,
    )
