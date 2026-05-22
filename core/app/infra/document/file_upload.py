"""Document file upload logic — composable infra architecture.

Canonical upload chain (mirrors app/infra/media/upload.py):

  uploads_entry
    └─ files_resource        (create_file_resource)
    └─ files_entry           (create_file_entry, files_id=resource.id — writes
       └─ file_files_connection  the resource↔entry link inline)
    └─ file_uploads_entry    (create_file_upload, file_id = ENTRY id)

The junction's ``file_id`` FKs ``files_entry`` — so it must be the ENTRY id, not
the resource id. (The previous impl created only a files_resource and handed its
id to the junction, which violated the FK on every upload.)

Soft/accept follows the canonical CRUD lifecycle (see persona/create):
  - ``soft=True`` → create the whole chain dormant (``active=False``) + a pending
    ``soft_calls_entry`` (the row ids stashed in ``patch``).
  - ``{idempotency_key, accept}`` → promote (``activate_rows`` on each row) or
    reject. Promote uses activate_rows (not re-create) since uploads aren't
    upsertable; structure is otherwise identical to persona/create.

Does NOT link the file to any document — that is a separate update operation.
"""

from __future__ import annotations

import os
import uuid as _uuid
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.document.types import FileUploadDocumentApiResponse
from app.infra.globals import UPLOAD_FOLDER
from app.infra.permissions_helpers import has_permission
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import create_file as create_file_resource
from app.utils.cache.invalidate_tags import invalidate_tags

ARTIFACT = "document"
OPERATION = "file_upload"


async def file_upload_document_impl(
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
) -> FileUploadDocumentApiResponse:
    """Upload a file for later use in documents (canonical chain + soft/accept).

    Soft-call key: ``soft_calls_entry.call_id`` FKs ``calls_entry``, so the
    pending row is keyed by the audit wrapper's server-minted ``call_id`` (not a
    client key). On a soft propose we stash it under ``call_id`` and echo it in
    the response; the ack arrives with ``idempotency_key`` set to that value.
    """
    # -- Profile context + permission (always) ----------------------------------
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401, detail="Profile not found. Please sign in again.",
        )
    if not has_permission(profile.role_permissions, "document", "file_upload"):
        raise HTTPException(
            status_code=403, detail="You don't have permission to upload document files.",
        )

    # ── Short-circuit: ack path (mirrors persona/create) ───────────────────────
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact=ARTIFACT)
        if entry is None or entry.status != "pending" or entry.operation != OPERATION:
            raise HTTPException(
                status_code=404, detail="No pending file upload for this call.",
            )
        ids = entry.patch or {}

        if accept:
            # Promote: uploads aren't upsertable, so flip the dormant chain active
            # (vs CRUD's re-create with soft=False). Same effect.
            async with pool.acquire() as conn:
                async with conn.transaction():
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="files_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="files_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="file_uploads_entry", ids=[UUID(ids["junction_id"])])
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

        await invalidate_tags(["uploads", "resources", "files"], redis=redis)
        return FileUploadDocumentApiResponse(
            file_id=entry.artifact_id, idempotency_key=idempotency_key,
        )

    # ── First-call requirements ───────────────────────────────────────────────
    if file_bytes is None or not filename:
        raise HTTPException(
            status_code=400,
            detail="A file is required for upload (or pass `idempotency_key` + "
            "`accept` for the ack call).",
        )

    # -- Write file to disk -----------------------------------------------------
    upload_uuid = _uuid.uuid4()
    _, ext = os.path.splitext(filename)
    if not ext:
        ext = ".bin"
    file_path = f"{upload_uuid}{ext}"
    full_path = UPLOAD_FOLDER / f"{upload_uuid}{ext}"
    with open(full_path, "wb") as f:
        f.write(file_bytes)

    # -- Create the canonical chain (dormant when soft) -------------------------
    session_uuid = session_id or UUID(int=0)
    async with pool.acquire() as conn:
        upload_result = await create_upload(
            conn,
            redis, session_id=session_uuid,
            file_path=file_path,
            mime_type=content_type,
            size=len(file_bytes),
            soft=soft,
        )
        resource = await create_file_resource(conn, redis, soft=soft)
        # The entry FKs the junction; it links back to the resource inline.
        file_entry = await create_file_entry(
            conn,
            redis, session_id=session_uuid,
            files_id=resource.id,
            soft=soft,
        )
        junction = await create_file_upload(
            conn,
            redis, file_id=file_entry.id,
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
                    "entry_id": str(file_entry.id),
                    "junction_id": str(junction.id),
                },
            )

    # -- Invalidate cache -------------------------------------------------------
    await invalidate_tags(["uploads", "resources", "files"], redis=redis)

    return FileUploadDocumentApiResponse(file_id=resource.id, idempotency_key=call_id)
