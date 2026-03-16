"""File writer utility — writes content to disk and creates uploads_entry records.

Provides `write_text_file()` and `write_json_file()` that:
1. Write content to UPLOAD_FOLDER/{subdir}/{uuid}.{ext}
2. Create an uploads entry via the canonical helper
3. Return the new upload_id for FK usage
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import UPLOAD_FOLDER
from app.infra.upload_paths import ensure_upload_subdir, resolve_upload_path
from app.tools.entries.uploads.create import create_upload


async def _create_upload_record(
    conn: asyncpg.Connection,
    relative_path: str,
    mime_type: str,
    size: int,
    session_id: UUID | None = None,
) -> UUID:
    """Create an uploads entry via the canonical black-box tool."""
    if session_id is None:
        raise ValueError("session_id is required to create uploads entries")

    return (
        await create_upload(
            conn,
            session_id=session_id,
            file_path=relative_path,
            mime_type=mime_type,
            size=size,
        )
    ).id


def read_text_file(file_path: str, *, upload_folder: Path = UPLOAD_FOLDER) -> str:
    """Read text content from an upload file path."""
    full_path = resolve_upload_path(file_path, upload_folder=upload_folder)
    return full_path.read_text(encoding="utf-8")


async def write_text_file(
    conn: asyncpg.Connection,
    session_id: UUID | None,
    content: str,
    *,
    upload_folder: Path = UPLOAD_FOLDER,
) -> UUID:
    """Write a .txt file and create an uploads_entry record.

    Returns the upload_id (uploads_entry.id).
    """
    text_folder = ensure_upload_subdir("text", upload_folder=upload_folder)
    file_id = str(uuid.uuid4())
    filename = f"{file_id}.txt"
    relative_path = f"text/{filename}"
    full_path = text_folder / filename

    data = content.encode("utf-8")
    full_path.write_bytes(data)

    return await _create_upload_record(
        conn,
        relative_path=relative_path,
        mime_type="text/plain",
        size=len(data),
        session_id=session_id,
    )


async def write_json_file(
    conn: asyncpg.Connection,
    session_id: UUID | None,
    data: dict[str, Any] | list[Any],
    *,
    subdir: str = "call",
    upload_folder: Path = UPLOAD_FOLDER,
) -> UUID:
    """Write a .json file and create an uploads_entry record.

    Args:
        conn: Database connection.
        session_id: Infrastructure session id.
        data: JSON-serializable payload.
        subdir: Sub-directory under UPLOAD_FOLDER (default "call").

    Returns the upload_id (uploads_entry.id).
    """
    folder = ensure_upload_subdir(subdir, upload_folder=upload_folder)

    file_id = str(uuid.uuid4())
    filename = f"{file_id}.json"
    relative_path = f"{subdir}/{filename}"
    full_path = folder / filename

    raw = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    full_path.write_bytes(raw)

    return await _create_upload_record(
        conn,
        relative_path=relative_path,
        mime_type="application/json",
        size=len(raw),
        session_id=session_id,
    )
