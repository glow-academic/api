"""Shared group resolve logic — canonical impl for every artifact's group endpoint.

Resolves or creates a time-windowed group, handles optional naming and
ack (idempotency) semantics, and optionally returns conversation history
in the shape the generation panel (GenerationPanel.flattenMessages) expects.

Per-artifact modules (app/infra/<artifact>/group.py) are thin wrappers that
declare an ARTIFACT_TYPE and per-artifact request/response types so
OpenAPI schemas remain named per artifact.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg


def _mint_group_id() -> UUID:
    """v7 UUID for chronological ordering; falls back to v4 on older Pythons."""
    return uuid.uuid7() if hasattr(uuid, "uuid7") else uuid.uuid4()
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.generation.chat_history import (
    annotate_audit_only,
    annotate_read_dedup,
    classify_tools_read_or_write,
    combine_keep_reasons,
)
from app.infra.group.refresh import refresh_group_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.calls.search import search_calls
from app.tools.entries.soft_calls.search import search_soft_calls
from app.tools.entries.group_names.create import create_group_name
from app.tools.entries.groups.create import create_group
from app.tools.entries.groups.get import get_groups
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
    """Shared request body — each artifact subclasses this for OpenAPI naming.

    Group resolve is a **read** — it returns the current group + history.
    Renaming is a separate write (``*_Title`` / ``title_group_impl``).
    """

    group_id: UUID | None = Field(
        None,
        description="Existing group UUID (omit to create or reuse via time window)",
    )
    snapshot_key: UUID | None = Field(
        None,
        description="Snapshot key for SETNX-race convergence on a single group "
        "across concurrent reads (e.g. parallel /context + /group + /search "
        "fan-out on page load). Echoed back in the response.",
    )


class GroupCall(BaseModel):
    """Tool call referenced by a message."""

    id: UUID
    tool_name: str | None = None
    template_name: str | None = None  # client-side alias
    # ``tool`` is the wire envelope (id/name/description/...) when a
    # tool resource is registered for this call. ``None`` means "no
    # tool" — the client renders an event pill instead of a tool
    # bubble. Same shape as the live audit ``.started``/``.completed``
    # events use, so the replay UI matches the streaming UI exactly.
    tool: dict[str, Any] | None = None

    # ── Soft-call ledger snapshot ─────────────────────────────────
    # Latest ``soft_calls_mv`` row for this call_id. ``None`` when the
    # call wasn't a soft write (no ledger entry → executed). When set,
    # the client renders Accept/Reject controls keyed on the call_id;
    # ``ledger_artifact_id`` + ``ledger_operation`` are echoed so the
    # client can correlate to the affected row without re-querying.
    ledger_status: str | None = None       # 'pending' | 'accepted' | 'rejected'
    ledger_operation: str | None = None    # 'create' | 'update' | 'delete' | 'duplicate'
    ledger_artifact: str | None = None     # 'persona' | 'scenario' | ...
    ledger_artifact_id: UUID | None = None


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
    in_context: bool = Field(
        True,
        description="Whether this message is included in the LLM context for the next "
        "generation. Mirrors the dedup pass that builds chat history (see in_context_reason).",
    )
    in_context_reason: str = Field(
        "kept",
        description="Why this message is in/out of LLM context. "
        "'kept' = included; 'deduped_read' = older read-only call to a tool that has "
        "a fresher result later in the group; future values may include 'trimmed_top_n'.",
    )


class GroupRun(BaseModel):
    """Run within a group, with its messages."""

    id: UUID
    created_at: datetime | None = None
    messages: list[GroupMessage] = Field(default_factory=list)


class GroupResolveResponse(BaseModel):
    """Shared response body — each artifact subclasses this for OpenAPI naming.

    Read-only: returns the resolved group + its current title + history.
    Renaming flows through ``*_Title`` / ``title_group_impl`` (write).
    """

    group_id: UUID = Field(..., description="Resolved or newly created group UUID")
    name: str | None = Field(
        None,
        description="The group's current title (latest active group_names_entry, "
        "or 'New Chat' fallback for freshly minted groups)",
    )
    snapshot_key: UUID | None = Field(
        None,
        description="Snapshot key echoed back — the UUID concurrent fan-out reads "
        "converged on via SETNX. Mirrors the resolved group_id.",
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
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
    snapshot_key: UUID | None = None,
    include_history: bool = True,
    **_kwargs,
) -> GroupResolveResponse:
    """Resolve or create a group, return its current title + history.

    Read-only:
      - ``group_id`` provided → reuse it (UPSERT a row if it doesn't yet
        exist — supports the client-minted id pattern), refresh the Redis
        window, optionally load history.
      - ``group_id`` omitted → check Redis window; if no active group,
        SETNX-claim a candidate id so concurrent fan-out reads converge
        on the same group.
      - Freshly minted groups carry a default ``"New Chat"`` title so
        the client never paints with an empty header. The AI later
        renames via ``*_Title`` (writes a fresh group_names_entry row).

    Renaming has been split out — call ``title_group_impl`` for that.
    """
    if request is not None:
        group_id = request.group_id
        snapshot_key = snapshot_key or request.snapshot_key

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
                soft=False,
            )
        resolved_group_id = result.id
        # Distinguish a fresh INSERT from a no-op upsert. Only the
        # former is "created_new" for the purposes of the MV refresh
        # decision — existing groups have content worth loading and
        # don't need a default title written over the AI's later rename.
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
            # Concurrent page-load fires multiple HTTP routes in
            # parallel (e.g. /context + /group + /search), each
            # arriving here with no active group in Redis. The naive
            # check-then-act mints THREE different groups, three
            # SETEX writes race, last-writer-wins — we end up with
            # audit rows fragmented across stranded groups.
            #
            # SET NX EX is the single-shot atomic claim Redis is
            # designed for. We propose a candidate id, try to claim
            # the slot. Whoever wins materializes the group; losers
            # read back the winner's id and proceed against it. All
            # concurrent calls converge on one group.
            candidate = snapshot_key or _mint_group_id()
            claimed = await redis.set(
                key, str(candidate), nx=True, ex=window_seconds,
            )
            if claimed:
                async with pool.acquire() as conn:
                    result = await create_group(
                        conn,
                        session_id=session_id,
                        artifact_type=artifact_type,
                        id=candidate,
                        soft=False,
                    )
                resolved_group_id = result.id
                created_new = True
            else:
                # Lost the race — winner has already populated the
                # key. Re-read and use the winner's id; the row
                # they minted with is_active=true is already FK-safe
                # for downstream audits.
                winner = await redis.get(key)
                if winner is None:
                    # Pathological: TTL expired between SETNX and
                    # GET. Fall back to minting our own — this is
                    # extremely unlikely (window_seconds is 30+ min).
                    async with pool.acquire() as conn:
                        result = await create_group(
                            conn,
                            session_id=session_id,
                            artifact_type=artifact_type,
                            id=candidate,
                            soft=False,
                        )
                    resolved_group_id = result.id
                    await redis.setex(key, window_seconds, str(resolved_group_id))
                    created_new = True
                else:
                    resolved_group_id = UUID(
                        winner.decode() if isinstance(winner, bytes) else winner
                    )
                    await redis.expire(key, window_seconds)

    # ── Default title for freshly-minted groups ──────────────────────
    # Write a "New Chat" row so the client never sees an empty header
    # between creation and the AI's first ``*_Title`` rename. ``groups_mv``
    # resolves to the latest active group_names_entry, so the AI's
    # later rename invisibly replaces this default.
    name: str | None = None
    if created_new:
        async with pool.acquire() as conn:
            await create_group_name(
                conn,
                group_id=resolved_group_id,
                name="New Chat",
                session_id=session_id,
            )
        name = "New Chat"
        await refresh_group_impl(
            pool, redis, profile_id=profile_id, session_id=session_id,
        )

    # ── Optional conversation history ────────────────────────────────
    runs_data: list[GroupRun] | None = None
    if include_history and not created_new:
        runs_data = await _load_history(pool, redis, resolved_group_id)

    # ── Resolve current title from groups_mv ─────────────────────────
    # When the group already existed, surface its latest title so the
    # SSR-rendered display name reflects the latest rename without a
    # separate round-trip.
    if name is None:
        async with pool.acquire() as conn:
            existing = await get_groups(conn, ids=[resolved_group_id])
        if existing:
            name = existing[0].name

    return GroupResolveResponse(
        group_id=resolved_group_id,
        name=name,
        snapshot_key=snapshot_key or resolved_group_id,
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

    # Batch-resolve tool resources via the canonical black box. Calls
    # with no registered tool get ``tool=None`` and the client renders
    # them as event pills rather than tool bubbles. ``tool_name`` /
    # ``template_name`` stay populated for legacy consumers that don't
    # yet read the full ``tool`` field.
    tool_ids = list({c.tool_id for c in call_items if c.tool_id})
    tool_resources = await get_tools(pool, tool_ids, redis) if tool_ids else []
    tool_by_id = {t.id: t for t in tool_resources if t.id}

    # Soft-call ledger snapshot per call_id (latest status from
    # ``soft_calls_mv``). Calls with no ledger row stay ``None`` —
    # those weren't soft writes. The chat panel reads these fields to
    # decide whether to render Accept/Reject controls; the client
    # doesn't parse ``arguments.soft`` (brittle) any more.
    call_ids_for_ledger = [c.id for c in call_items]
    async with pool.acquire() as conn:
        ledger_entries = (
            await search_soft_calls(conn, call_ids=call_ids_for_ledger, limit=len(call_ids_for_ledger) or 1)
            if call_ids_for_ledger else []
        )
    ledger_by_call_id = {e.call_id: e for e in ledger_entries}

    calls_by_id: dict[UUID, GroupCall] = {}
    for c in call_items:
        tool_resource = tool_by_id.get(c.tool_id) if c.tool_id else None
        tool_name = tool_resource.name if tool_resource else None
        ledger = ledger_by_call_id.get(c.id)
        calls_by_id[c.id] = GroupCall(
            id=c.id,
            tool_name=tool_name,
            template_name=tool_name,
            tool=tool_resource.model_dump(mode="json") if tool_resource else None,
            ledger_status=ledger.status if ledger else None,
            ledger_operation=ledger.operation if ledger else None,
            ledger_artifact=ledger.artifact if ledger else None,
            ledger_artifact_id=ledger.artifact_id if ledger else None,
        )

    msgs_by_run: dict[UUID, list] = defaultdict(list)
    for m in msg_items:
        msgs_by_run[m.run_id].append(m)

    # Flat asc-by-time list of (run_idx, msg) pairs so we can run the
    # group-wide dedup pass once and assign annotations back per message.
    flat: list[tuple[int, Any]] = []
    for run_idx, run_item in enumerate(run_items):
        for m in msgs_by_run.get(run_item.run_id, []):
            flat.append((run_idx, m))

    # Map each call_id → tool_id (from the entries we already loaded),
    # then build per-message tool_id sets for the dedup pass + audit
    # triples (has_real_tool, has_user_text, has_any_calls).
    tool_id_by_call_id: dict[UUID, UUID] = {
        c.id: c.tool_id for c in call_items if c.tool_id
    }
    tool_ids_per_msg: list[set[UUID]] = []
    audit_per_msg: list[tuple[bool, bool]] = []
    for _, m in flat:
        msg_call_ids = list(m.call_ids or [])
        tool_ids_here = {
            tool_id_by_call_id[cid] for cid in msg_call_ids if cid in tool_id_by_call_id
        }
        has_real_tool = bool(tool_ids_here)
        has_any_calls = bool(msg_call_ids)
        tool_ids_per_msg.append(tool_ids_here)
        audit_per_msg.append((has_real_tool, has_any_calls))

    all_tool_ids = list({tid for s in tool_ids_per_msg for tid in s})
    async with pool.acquire() as conn:
        is_write_by_tool = await classify_tools_read_or_write(conn, all_tool_ids)
    audit_anns = annotate_audit_only(audit_per_msg)
    dedup_anns = annotate_read_dedup(tool_ids_per_msg, is_write_by_tool)
    annotations = combine_keep_reasons(audit_anns, dedup_anns)

    runs_data: list[GroupRun] = [
        GroupRun(
            id=run_item.run_id,
            created_at=getattr(run_item, "run_created_at", None),
            messages=[],
        )
        for run_item in run_items
    ]
    for (run_idx, m), (in_context, reason) in zip(flat, annotations):
        call_ids = list(m.call_ids or [])
        runs_data[run_idx].messages.append(
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
                in_context=in_context,
                in_context_reason=reason,
            )
        )
    return runs_data
