"""Shared group resolve logic — canonical impl for every artifact's group endpoint.

Resolves or creates a time-windowed group, handles optional naming and
ack (idempotency) semantics, and optionally returns conversation history
in the shape the generation panel (GenerationPanel.flattenMessages) expects.

Per-artifact modules (app/infra/<artifact>/group.py) are thin wrappers that
declare an ARTIFACT_TYPE and per-artifact request/response types so
OpenAPI schemas remain named per artifact.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.group.refresh import refresh_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.search import search_calls
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.search import search_runs
from app.tools.resources.tools.get import get_tools

DEFAULT_WINDOW_SECONDS = 60


def _redis_key(artifact_type: str, profile_id: UUID) -> str:
    return f"artifact_group:{artifact_type}:{profile_id}"


# ---------------------------------------------------------------------------
# Shared request/response base models
# ---------------------------------------------------------------------------


class GroupResolveRequest(BaseModel):
    """Shared request body — each artifact subclasses this for OpenAPI naming."""

    group_id: UUID | None = Field(
        None,
        description="Existing group UUID (omit to create or reuse via time window)",
    )
    name: str | None = Field(None, description="Optional name for the group")
    idempotency_key: UUID | None = Field(
        None,
        description="Operation key for ack — promotes or rejects a dormant group",
    )
    accept: bool = Field(
        True,
        description="Accept (promote) or reject dormant state. Only meaningful with idempotency_key",
    )


class GroupCall(BaseModel):
    """Tool call referenced by a message."""

    id: UUID
    tool_name: str | None = None
    template_name: str | None = None  # client-side alias


class GroupMessage(BaseModel):
    """Message within a run."""

    id: UUID
    role: str
    created_at: datetime | None = None
    text_ids: list[UUID] = Field(default_factory=list)
    audio_ids: list[UUID] = Field(default_factory=list)
    image_ids: list[UUID] = Field(default_factory=list)
    video_ids: list[UUID] = Field(default_factory=list)
    file_ids: list[UUID] = Field(default_factory=list)
    call_ids: list[UUID] = Field(default_factory=list)
    calls: list[GroupCall] = Field(default_factory=list)


class GroupRun(BaseModel):
    """Run within a group, with its messages."""

    id: UUID
    created_at: datetime | None = None
    messages: list[GroupMessage] = Field(default_factory=list)


class GroupResolveResponse(BaseModel):
    """Shared response body — each artifact subclasses this for OpenAPI naming."""

    group_id: UUID = Field(..., description="Resolved or newly created group UUID")
    group_name_id: UUID | None = Field(
        None,
        description="UUID of the created group_names entry (if name was provided)",
    )
    name: str | None = Field(None, description="The name that was set (if provided)")
    idempotency_key: UUID | None = Field(
        None, description="Idempotency key echoed back for client correlation"
    )
    runs: list[GroupRun] | None = Field(
        None,
        description="Conversation history — populated when resolving an existing group for fetch",
    )


# ---------------------------------------------------------------------------
# Impl
# ---------------------------------------------------------------------------


async def resolve_group_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact_type: str,
    profile_id: UUID,
    session_id: UUID,
    request: GroupResolveRequest | None = None,
    group_id: UUID | None = None,
    name: str | None = None,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    include_history: bool = True,
    **_kwargs,
) -> GroupResolveResponse:
    """Resolve or create a group with optional naming and conversation history.

    Behavior:
      - ack path: accept+idempotency_key → promote/reject dormant group.
      - group_id provided → reuse it, refresh window, optionally load history.
      - group_id omitted → check Redis window; create fresh groups_entry if none.
      - name provided → create group_names_entry for the resolved group.

    History is loaded when ``include_history`` is True AND the call is a
    pure fetch (existing group_id, no naming, no creation). That keeps the
    request-to-write flow (create / name) response lean.
    """
    if request is not None:
        group_id = request.group_id
        name = request.name
        idempotency_key = idempotency_key or request.idempotency_key
        if idempotency_key and accept is None:
            accept = request.accept

    # ── Ack short-circuit ─────────────────────────────────────────────
    if accept is not None and idempotency_key is not None:
        if accept:
            async with pool.acquire() as conn:
                await create_group(
                    conn,
                    session_id=session_id,
                    artifact_type=artifact_type,
                    id=idempotency_key,
                    soft=False,
                )
            await refresh_group_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
        return GroupResolveResponse(
            group_id=idempotency_key,
            group_name_id=None,
            name=name,
            idempotency_key=idempotency_key,
        )

    # ── Profile context ───────────────────────────────────────────────
    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Resolve or create group ───────────────────────────────────────
    resolved_group_id: UUID
    created_new = False

    if group_id is not None:
        # Client-minted id pattern: the caller treats ``group_id`` as
        # canonical and the server idempotently materializes the row.
        # ``create_group`` is an UPSERT (``ON CONFLICT (id) DO UPDATE``)
        # so this is a no-op when the row already exists. Lets the
        # client pre-latch the URL synchronously and the server fill
        # in the rest — same pattern ``draftId`` already uses.
        async with pool.acquire() as conn:
            result = await create_group(
                conn,
                session_id=session_id,
                artifact_type=artifact_type,
                id=group_id,
                soft=soft,
            )
        resolved_group_id = result.id
        # Distinguish a fresh INSERT from a no-op upsert. Only the
        # former is "created_new" for the purposes of the MV refresh
        # decision and the history-load skip — existing groups have
        # content worth loading.
        created_new = result.inserted
        await redis.setex(
            _redis_key(artifact_type, profile_id), window_seconds, str(resolved_group_id),
        )
    else:
        key = _redis_key(artifact_type, profile_id)
        existing = await redis.get(key)
        if existing:
            resolved_group_id = UUID(
                existing.decode() if isinstance(existing, bytes) else existing
            )
            await redis.expire(key, window_seconds)
        else:
            async with pool.acquire() as conn:
                result = await create_group(
                    conn,
                    session_id=session_id,
                    artifact_type=artifact_type,
                    id=idempotency_key,
                    soft=soft,
                )
            resolved_group_id = result.id
            await redis.setex(key, window_seconds, str(resolved_group_id))
            created_new = True

    # ── Optional naming ───────────────────────────────────────────────
    group_name_id: UUID | None = None
    if name:
        async with pool.acquire() as conn:
            name_result = await create_group_name(
                conn,
                group_id=resolved_group_id,
                name=name,
                session_id=session_id,
            )
            group_name_id = name_result.id

    # ── Canonical refresh (only if we wrote something) ───────────────
    if created_new or group_name_id:
        await refresh_group_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )

    # ── Optional conversation history ────────────────────────────────
    runs_data: list[GroupRun] | None = None
    if include_history and not created_new and not name:
        runs_data = await _load_history(pool, redis, resolved_group_id)

    return GroupResolveResponse(
        group_id=resolved_group_id,
        group_name_id=group_name_id,
        name=name,
        idempotency_key=idempotency_key or resolved_group_id,
        runs=runs_data,
    )


async def _load_history(
    pool: asyncpg.Pool, redis: Redis, group_id: UUID,
) -> list[GroupRun]:
    """Return runs→messages→calls shaped for GenerationPanel.flattenMessages."""
    async with pool.acquire() as conn:
        run_items, _ = await search_runs(
            conn, group_ids=[group_id], sort_order="asc", limit=10000,
        )
    if not run_items:
        return []

    run_ids = [r.run_id for r in run_items]
    async with pool.acquire() as conn:
        msg_items, _ = await search_messages(
            conn, run_ids=run_ids, sort_order="asc", limit=100000,
        )
        call_items = await search_calls(conn, run_ids=run_ids, limit=100000)

    tool_ids = list({c.tool_id for c in call_items if c.tool_id})
    tool_name_map: dict[UUID, str] = {}
    if tool_ids:
        tool_resources = await get_tools(pool, tool_ids, redis)
        tool_name_map = {t.id: t.name for t in tool_resources if t.id and t.name}

    calls_by_id: dict[UUID, GroupCall] = {}
    for c in call_items:
        tool_name = tool_name_map.get(c.tool_id) if c.tool_id else None
        calls_by_id[c.id] = GroupCall(
            id=c.id, tool_name=tool_name, template_name=tool_name,
        )

    msgs_by_run: dict[UUID, list] = defaultdict(list)
    for m in msg_items:
        msgs_by_run[m.run_id].append(m)

    runs_data: list[GroupRun] = []
    for run_item in run_items:
        group_messages: list[GroupMessage] = []
        for m in msgs_by_run.get(run_item.run_id, []):
            call_ids = list(m.call_ids or [])
            group_messages.append(
                GroupMessage(
                    id=m.message_id,
                    role=m.role,
                    created_at=getattr(m, "message_created_at", None),
                    text_ids=list(m.text_ids or []),
                    audio_ids=list(m.audio_ids or []),
                    image_ids=list(m.image_ids or []),
                    video_ids=list(m.video_ids or []),
                    file_ids=list(m.file_ids or []),
                    call_ids=call_ids,
                    calls=[calls_by_id[cid] for cid in call_ids if cid in calls_by_id],
                )
            )
        runs_data.append(
            GroupRun(
                id=run_item.run_id,
                created_at=getattr(run_item, "run_created_at", None),
                messages=group_messages,
            )
        )
    return runs_data
