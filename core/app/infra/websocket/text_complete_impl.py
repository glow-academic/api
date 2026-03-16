"""Text complete handler — pure business logic with emit: EmitFn.

Saves assistant message to DB on text_complete using persist_run_message.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

import asyncpg

from app.infra.websocket.persist_run_message import persist_run_message
from app.infra.websocket.socket_event import EmitFn
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def text_complete_impl(
    data: dict[str, Any],
    *,
    emit: EmitFn,
    conn: asyncpg.Connection,
    upload_folder: Path | None = None,
) -> None:
    """Save assistant message on text_complete."""
    event_type = data.get("event_type")
    if event_type != "text_complete":
        return

    run_id = data.get("run_id")
    session_id = data.get("session_id")
    final_content = data.get("text") or ""
    if not run_id or not session_id or not final_content:
        return

    try:
        await persist_run_message(
            conn,
            run_id=UUID(run_id),
            session_id=UUID(session_id),
            role="assistant",
            content=final_content,
            upload_folder=upload_folder,
        )
    except Exception as e:
        logger.exception(f"Failed to save text_complete message: {e}")
