"""Create a message on an existing run linked to a text upload.

Building block: message + text + text_upload junction + message_upload junction.
Used by create_tool_call (tool output) and persist_run_message (generation input).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

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
    redis: Redis,
    *,
    run_id: UUID,
    session_id: UUID,
    role: str,
    upload_id: UUID,
    mcp: bool = False,
    reasoning: bool = False,
    agent_ids: list[UUID] | None = None,
    created_at: "datetime | None" = None,
    id: UUID | None = None,
) -> CreateRunMessageResult:
    """Create a message on a run linked to a text upload.

    Chain: create_message → create_text → create_text_upload → create_message_upload.

    ``created_at`` overrides the message row's timestamp — used by the
    audit framework so the tool-call message sorts at dispatch time
    rather than completion time. ``None`` (default) stamps ``now()``.

    ``id`` lets the caller pre-mint the ``messages_entry.id`` so a
    pre-rendered FE skeleton (created on a ``*.image.start`` event keyed
    by this id) can be located and replaced when ``*.image.complete``
    arrives carrying the same id. ``None`` (default) lets the underlying
    INSERT generate a fresh ``uuidv7()``.

    ``reasoning`` flags the underlying ``messages_entry`` row as a
    chain-of-thought trace (default false — normal message). The text +
    upload junctions are written the same way regardless.
    """
    message = await create_message(
        conn, redis, run_id=run_id, role=role, mcp=mcp, reasoning=reasoning,
        agent_ids=agent_ids, created_at=created_at, id=id,
    )

    text = await create_text(conn, redis, session_id=session_id, mcp=mcp)

    text_upload_junction = await create_text_upload(
        conn, redis,
        text_id=text.id,
        upload_id=upload_id,
        session_id=session_id,
        mcp=mcp,
    )

    message_upload_junction = await create_message_upload(
        conn, redis,
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
