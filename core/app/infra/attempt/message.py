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
    auto_link_parent: bool = True,
    **_kwargs,
) -> AttemptMessageInternalResult:
    """Create an attempt message with content entries.

    Accepts either:
    - Simple: text="hello", persona_id=UUID → one content block
    - Structured: contents=[{content: "...", persona_id: "..."}, ...] → multiple blocks

    Parent-message semantics:
    - If `parent_message_id` is provided, it's used verbatim — an edge
      is written in attempt_message_tree_entry.
    - If `parent_message_id` is None AND `auto_link_parent` is True
      (default), the impl resolves the chat's latest prior message and
      uses it as the parent. Keeps linear chats as proper degenerate
      trees without any client work.
    - If `parent_message_id` is None AND `auto_link_parent` is False,
      no parent is written — the message is an explicit tree root.
      Forks use this to root-branch when the fork target has no parent.
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
    from app.tools.entries.attempt_message.search import search_attempt_messages
    from app.tools.entries.attempt_message_tree.create import (
        create_attempt_message_tree,
    )

    effective_session_id = session_id or profile.session_id

    async with pool.acquire() as conn:
        # Auto-link to the chat's latest prior message when the caller
        # didn't specify one AND opted into auto-link (the default).
        # Makes every non-root message an explicit child of some parent
        # in attempt_message_tree_entry, giving the MV's parent_message_id
        # projection + sibling computation something to land on.
        #
        # Callers that want to override:
        #   - Fork mid-chat: pass an explicit parent_message_id.
        #   - Fork a root: pass parent_message_id=None AND
        #     auto_link_parent=False → new message becomes a sibling
        #     root alongside the original.
        #
        # search_attempt_messages orders DESC by created_at and the
        # MV is auto-resolved on pull, so items[0] is the newest
        # active message in the chat.
        if parent_message_id is None and auto_link_parent:
            latest_items, _ = await search_attempt_messages(
                conn, chat_ids=[chat_id], limit=1
            )
            if latest_items:
                parent_message_id = latest_items[0].message_id

        # Create attempt_message_entry (container)
        message_result = await create_attempt_message(
            conn,
            chat_id=chat_id,
            session_id=effective_session_id,
        )

        # Create attempt_content_entry for each content block
        content_ids = []
        for content_text, content_persona_id in content_items:
            content_result = await create_attempt_content(
                conn,
                message_id=message_result.id,
                session_id=effective_session_id,
                content=content_text,
                persona_id=content_persona_id or uuid_mod.UUID(int=0),
            )
            content_ids.append(str(content_result.id))

        # Connect to the parent in the tree. First message in a chat
        # stays unparented (parent_message_id is None after the search
        # above returned nothing) — MV's LEFT JOIN returns null for
        # roots, which is the expected shape.
        if parent_message_id is not None:
            await create_attempt_message_tree(
                conn,
                parent_id=parent_message_id,
                child_id=message_result.id,
                session_id=effective_session_id,
            )

    # Refresh MVs so messages appear in the UI
    from app.tools.entries.attempt_content.refresh import refresh_attempt_content
    from app.tools.entries.attempt_message.refresh import refresh_attempt_message
    async with pool.acquire() as conn:
        await refresh_attempt_message(conn)
        await refresh_attempt_content(conn)

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
