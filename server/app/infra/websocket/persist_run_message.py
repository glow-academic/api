"""Persist a text message on an existing run — for generation input messages.

Composes: save_text_upload + create_upload + create_run_message.
Used by the generate_prepare handler to persist system/developer/user messages.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

import asyncpg

from app.infra.tools.entries.create_run_message import (
    CreateRunMessageResult,
    create_run_message,
)
from app.infra.tools.entries.save_text_upload import save_text_upload
from app.tools.entries.uploads.create import create_upload


async def persist_run_message(
    conn: asyncpg.Connection,
    *,
    run_id: UUID,
    session_id: UUID,
    role: str,
    content: str,
    upload_folder: Path | None = None,
    agent_ids: list[UUID] | None = None,
) -> CreateRunMessageResult:
    """Write text to disk, create upload record, and link to a message on a run.

    When upload_folder is None, resolves from globals (production path).
    Pass explicitly for testing.
    """
    if upload_folder is None:
        from app.infra.globals import UPLOAD_FOLDER

        upload_folder = UPLOAD_FOLDER

    # 1. Write text file to disk
    upload_id = uuid4()
    rel_path = save_text_upload(content, upload_id, upload_folder)
    full_path = upload_folder / rel_path
    size = full_path.stat().st_size

    # 2. Create upload DB record
    upload_result = await create_upload(
        conn,
        session_id=session_id,
        file_path=rel_path,
        mime_type="text/plain",
        size=size,
    )

    # 3. Create message + text + junctions
    return await create_run_message(
        conn,
        run_id=run_id,
        session_id=session_id,
        role=role,
        upload_id=upload_result.id,
        agent_ids=agent_ids,
    )
