"""Create a message on an existing run linked to a text upload.

Building block: message + text + text_upload junction + message_upload junction.
Used by create_tool_call (tool output) and persist_run_message (generation input).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import asyncpg

from app.tools.entries.message_uploads.create import create_message_upload
from app.tools.entries.messages.create import create_message
from app.tools.entries.text_uploads.create import create_text_upload
from app.tools.entries.texts.create import create_text


@dataclass(frozen=True)
class CreateRunMessageResult:
    message_id: UUID
    text_id: UUID
    text_upload_junction_id: UUID
    message_upload_junction_id: UUID


async def create_run_message(
    conn: asyncpg.Connection,
    *,
    run_id: UUID,
    session_id: UUID,
    role: str,
    upload_id: UUID,
    mcp: bool = False,
    agent_ids: list[UUID] | None = None,
) -> CreateRunMessageResult:
    """Create a message on a run linked to a text upload.

    Chain: create_message → create_text → create_text_upload → create_message_upload.
    """
    message = await create_message(
        conn, run_id=run_id, role=role, mcp=mcp, agent_ids=agent_ids
    )

    text = await create_text(conn, session_id=session_id, mcp=mcp)

    text_upload_junction = await create_text_upload(
        conn,
        text_id=text.id,
        upload_id=upload_id,
        session_id=session_id,
        mcp=mcp,
    )

    message_upload_junction = await create_message_upload(
        conn,
        message_id=message.id,
        upload_id=upload_id,
        session_id=session_id,
        mcp=mcp,
    )

    # Flag the chat-data MVs so the scheduler refreshes them within
    # the next ~2s interval. Without this the MVs stay frozen — the
    # scheduler is purely pending-driven, and nothing else in the
    # normal artifact-write path enqueues runs_mv / messages_mv /
    # calls_mv. Both the UI panel and chat-history threading read
    # through these MVs, so a missed enqueue means stale data for
    # both consumers. Best effort — never fail the audit write.
    try:
        from app.infra.globals import get_redis_client
        from app.utils.cache.mv_refresh_queue import enqueue_pending
        redis = get_redis_client()
        for target in ("runs_mv", "messages_mv", "calls_mv"):
            await enqueue_pending(redis, target)
    except Exception:
        pass

    return CreateRunMessageResult(
        message_id=message.id,
        text_id=text.id,
        text_upload_junction_id=text_upload_junction.id,
        message_upload_junction_id=message_upload_junction.id,
    )
