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
from app.infra.server_timing import timed
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
    audios_id: UUID | None = None,
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
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id,
        )
    if profile is None:
        raise HTTPException(status_code=401, detail="Profile not found.")

    # Create entries using black boxes
    from app.tools.entries.attempt_chat.get import get_attempt_chats
    from app.tools.entries.attempt_content.create import create_attempt_content
    from app.tools.entries.attempt_message.create import create_attempt_message
    from app.tools.entries.attempt_message.get import get_attempt_messages
    from app.tools.entries.attempt_message_completion.create import (
        create_attempt_message_completion,
    )
    from app.tools.entries.attempt_message.search import search_attempt_messages
    from app.tools.entries.attempt_message_tree.create import (
        create_attempt_message_tree,
    )
    from app.tools.resources.audios.get import get_audio_resource

    effective_session_id = session_id or profile.session_id

    with timed("db_write"):
     async with pool.acquire() as conn:
        # Pre-validate the chat exists BEFORE any write. The message insert
        # carries a hard FK (attempt_message_entry.chat_id → attempt_chat_entry);
        # a stale/bogus chat_id would otherwise surface as an uncaught
        # asyncpg.ForeignKeyViolationError and bubble out of the route as a raw
        # 500 (the route only maps ValueError → 400). Resolve via the existing
        # black-box getter (same pattern as the voice adapter) and fail with a
        # clean 404 — HTTPException propagates cleanly through
        # run_artifact_operation_with_audit, mirroring the impl's other 400/401
        # guards.
        chat_entries = await get_attempt_chats(conn, [chat_id], redis)
        if not chat_entries:
            raise HTTPException(status_code=404, detail="chat not found")

        # Pre-validate the two OTHER client-supplied FK references the same
        # way (#299 only closed chat_id). Both are raw UUIDs off the request:
        #   - parent_message_id → attempt_message_tree_entry.parent_id FK to
        #     attempt_message_entry(id). A stale fork target would raise an
        #     uncaught ForeignKeyViolationError on the tree insert below.
        #   - audios_id → attempt_audio_entry.audios_id FK to
        #     audios_resource(id). A stale attachment id would raise the same
        #     on the audio insert below.
        # Resolve each via its black-box getter and fail with a clean 404
        # (propagates through the audit wrapper) instead of a raw 500. Only the
        # explicit, client-supplied parent_message_id is checked here — the
        # auto-linked parent (resolved from search_attempt_messages below) is
        # server-derived and always valid.
        if parent_message_id is not None:
            parent_entries = await get_attempt_messages(
                conn, [parent_message_id], redis
            )
            if not parent_entries:
                raise HTTPException(
                    status_code=404, detail="parent message not found"
                )
        if audios_id is not None:
            audios_uuid = (
                audios_id if isinstance(audios_id, UUID) else UUID(str(audios_id))
            )
            if await get_audio_resource(conn, audios_uuid) is None:
                raise HTTPException(status_code=404, detail="audio not found")

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
                conn, redis, chat_ids=[chat_id], limit=1
            )
            if latest_items:
                parent_message_id = latest_items[0].message_id

        # Wrap the whole message+content+tree+completion+audio write
        # sequence in a single DB transaction so it commits all-or-nothing.
        # Previously these ran on the bare autocommit pool connection: the
        # message + content rows committed BEFORE the tree/audio inserts, so a
        # downstream failure (e.g. the persona guard, or — pre-#299-completion
        # — a bad parent/audio FK) left a DANGLING message row with no parent
        # edge and no audio. The transaction rolls the message back on any
        # failure. (Redis write-back inside the create_* calls is not
        # transactional, same caveat as every other conn.transaction() impl;
        # the MV refresh stays OUTSIDE the txn — it only runs on success.)
        async with conn.transaction():
            # Create attempt_message_entry (container)
            message_result = await create_attempt_message(
                conn, redis,
                chat_id=chat_id,
                session_id=effective_session_id,
            )

            # Create attempt_content_entry for each content block
            content_ids = []
            for content_text, content_persona_id in content_items:
                # ``persona_id`` FKs to ``personas_entry(id)`` (NOT NULL). The old
                # ``or UUID(int=0)`` fallback inserted the all-zero UUID when no
                # persona was supplied, which has no personas_entry row → an
                # uncaught ForeignKeyViolationError that crashed the socket task
                # ("Task exception was never retrieved"). Fail loud and early with
                # a clear, client-facing message instead. Callers must pass a real
                # persona entry id (e.g. the attempt's ``user_persona_id`` for the
                # learner, or an assistant persona for the reply).
                if not content_persona_id:
                    raise ValueError(
                        "persona_id is required to post a chat message — pass the "
                        "attempt's user_persona_id (learner) or an assistant "
                        "persona_id. None/empty is not allowed."
                    )
                content_result = await create_attempt_content(
                    conn, redis,
                    message_id=message_result.id,
                    session_id=effective_session_id,
                    content=content_text,
                    persona_id=content_persona_id,
                )
                content_ids.append(str(content_result.id))

            # Connect to the parent in the tree. First message in a chat
            # stays unparented (parent_message_id is None after the search
            # above returned nothing) — MV's LEFT JOIN returns null for
            # roots, which is the expected shape.
            if parent_message_id is not None:
                await create_attempt_message_tree(
                    conn, redis,
                    parent_id=parent_message_id,
                    child_id=message_result.id,
                    session_id=effective_session_id,
                )

            await create_attempt_message_completion(
                conn, redis,
                attempt_message_id=message_result.id,
                session_id=effective_session_id,
            )

            # Optional audio attachment: when the caller transcribed a mic
            # recording, the ``audios_id`` rides on the create request and we
            # link it to this fresh message via ``attempt_audio_entry`` — the
            # same junction the realtime adapter uses for assistant audio.
            # Keeping this inline (instead of a separate post-hoc call) gives
            # us a single atomic write and avoids the message briefly
            # existing without its audio in the MV.
            if audios_id is not None:
                audios_uuid = audios_id if isinstance(audios_id, UUID) else UUID(str(audios_id))
                from app.tools.entries.attempt_audio.create import (
                    create_attempt_audio,
                )
                await create_attempt_audio(
                    conn, redis,
                    message_id=message_result.id,
                    audios_id=audios_uuid,
                    session_id=effective_session_id,
                )

    # Refresh MVs so messages appear in the UI
    # (audio-link MV is best-effort — there's no attempt_audio_mv in the
    # registry, so we don't enqueue one here even when audios_id is set.)
    # ``attempt_message_tree_mv`` is enqueued whenever we wrote a tree edge
    # above (create_attempt_message_tree) — the tree MV reads directly from
    # attempt_message_tree_mv (get/search SELECT * FROM it), and the
    # MVRefresher worker only runs a target when something enqueues it, so
    # omitting it would leave the new parent/child edge invisible (stale
    # parent_message_id / sibling projection) until a manual refresh.
    refresh_targets = [
        "attempt_content_mv",
        "attempt_message_completion_mv",
        "attempt_message_mv",
    ]
    if parent_message_id is not None:
        refresh_targets.append("attempt_message_tree_mv")
    from app.infra.attempt.refresh import refresh_attempt_impl
    with timed("refresh"):
        await refresh_attempt_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
            targets=refresh_targets,
        )

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
