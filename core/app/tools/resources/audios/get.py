"""Audios Resource GET — reusable data-access layer.

Canonical readers for ``audios_resource`` and the full chain back to the
raw file on disk. Used by STT (to locate the PCM for transcription) and
by any future audio download endpoint.
"""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.uploads.types import GetUploadResponse
from app.tools.resources.audios.types import GetAudioResponse


async def get_audio_resource(
    conn: asyncpg.Connection,
    audios_id: UUID,
) -> GetAudioResponse | None:
    """Resolve a resource-level ``audios_id`` to its ``audios_resource`` row.

    This is the exact FK target of ``attempt_audio_entry.audios_id`` (and
    ``audios_audios_connection.audios_id``). Callers that accept a
    client-supplied ``audios_id`` use this to pre-validate the reference
    before any write — a missing resource surfaces as a clean 404 instead of
    an uncaught ``ForeignKeyViolationError`` raw-500. Unlike
    ``get_upload_by_audios_id`` (which requires the full bytes chain), this
    checks only the resource's existence, so a freshly-promoted resource with
    no uploads yet still validates.
    """
    row = await conn.fetchrow(
        """
        SELECT id, name, description, created_at, active, generated, mcp
        FROM audios_resource
        WHERE id = $1
        """,
        audios_id,
    )
    if row is None:
        return None
    return GetAudioResponse(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        active=row["active"],
        generated=row["generated"],
        mcp=row["mcp"],
    )


async def get_upload_by_audios_id(
    conn: asyncpg.Connection,
    audios_id: UUID,
) -> GetUploadResponse | None:
    """Resolve a resource-level ``audios_id`` down to the raw upload row.

    Join chain:
      ``audios_resource → audios_audios_connection → audios_entry
        → audio_uploads_entry → uploads_entry``

    Returns the first active upload linked to the resource, or ``None`` if
    the resource has no associated audio bytes yet.
    """
    row = await conn.fetchrow(
        """
        SELECT u.id, u.session_id, u.file_path, u.mime_type, u.size,
               u.created_at, u.active, u.mcp, u.generated
        FROM audios_resource ar
        JOIN audios_audios_connection aac
            ON aac.audios_id = ar.id AND aac.active = true
        JOIN audios_entry ae
            ON ae.id = aac.audio_id AND ae.active = true
        JOIN audio_uploads_entry aue
            ON aue.audio_id = ae.id AND aue.active = true
        JOIN uploads_entry u
            ON u.id = aue.upload_id AND u.active = true
        WHERE ar.id = $1 AND ar.active = true
        ORDER BY u.created_at DESC
        LIMIT 1
        """,
        audios_id,
    )
    if row is None:
        return None
    return GetUploadResponse(
        id=row["id"],
        session_id=row["session_id"],
        file_path=row["file_path"],
        mime_type=row["mime_type"],
        size=row["size"],
        created_at=row["created_at"],
        active=row["active"],
        mcp=row["mcp"],
        generated=row["generated"],
    )
