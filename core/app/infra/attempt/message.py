"""Attempt message — canonical create.

Creates attempt_message_entry + attempt_content_entry rows.
No generation, no events, no workflows.
Generation is triggered separately by the client via /attempt/generate.
"""

from __future__ import annotations

import uuid as uuid_mod
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


class AttemptMessageInternalResult(BaseModel):
    success: bool = True
    chat_id: str
    message_id: str | None = None
    content_ids: list[str] = Field(default_factory=list)


async def attempt_message_internal_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    # Message fields
    chat_id: UUID | None = None,
    attempt_id: UUID | None = None,
    text: str | None = None,
    message: str | None = None,
    persona_id: UUID | None = None,
    contents: list[dict] | None = None,
    parent_message_id: UUID | None = None,
    **_kwargs,
) -> AttemptMessageInternalResult:
    """Create an attempt message with content entries.

    Accepts either:
    - Simple: text="hello", persona_id=UUID → one content block
    - Structured: contents=[{content: "...", persona_id: "..."}, ...] → multiple blocks
    """
    if not chat_id:
        raise HTTPException(status_code=400, detail="chat_id is required")

    # Build content items: list of (content_text, persona_id) tuples
    content_items: list[tuple[str, UUID | None]] = []
    if contents:
        for c in contents:
            c_text = (c.get("content") or "").strip()
            c_persona = c.get("persona_id")
            if c_persona and isinstance(c_persona, str):
                c_persona = UUID(c_persona)
            if c_text:
                content_items.append((c_text, c_persona))
    else:
        resolved_text = (text or message or "").strip()
        if not resolved_text:
            raise HTTPException(status_code=400, detail="text or contents is required")
        if persona_id and isinstance(persona_id, str):
            persona_id = UUID(persona_id)
        content_items.append((resolved_text, persona_id))

    # Resolve profile
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found.")

    # Create entries using black boxes
    from app.tools.entries.attempt_content.create import create_attempt_content
    from app.tools.entries.attempt_message.create import create_attempt_message
    from app.tools.entries.calls.create import create_call
    from app.tools.entries.runs.create import create_run

    effective_session_id = session_id or profile.session_id

    async with pool.acquire() as conn:
        # Run + call for this message
        run_result = await create_run(
            conn,
            session_id=effective_session_id,
            group_id=profile.group_id,
        )
        call_result = await create_call(
            conn,
            run_id=run_result.id,
            session_id=effective_session_id,
        )

        # Create attempt_message_entry (container)
        message_result = await create_attempt_message(
            conn,
            chat_id=chat_id,
            message_id=run_result.id,
            call_id=call_result.id,
        )

        # Create attempt_content_entry for each content block
        content_ids = []
        for content_text, content_persona_id in content_items:
            content_result = await create_attempt_content(
                conn,
                message_id=message_result.id,
                call_id=call_result.id,
                content=content_text,
                persona_id=content_persona_id or uuid_mod.UUID(int=0),
            )
            content_ids.append(str(content_result.id))

    logger.info(
        f"Attempt message created: chat_id={chat_id}, "
        f"message_id={message_result.id}, contents={len(content_ids)}"
    )

    return AttemptMessageInternalResult(
        success=True,
        chat_id=str(chat_id),
        message_id=str(message_result.id),
        content_ids=content_ids,
    )
