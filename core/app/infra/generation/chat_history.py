"""Group-level chat history for LLM context threading.

When a generation kicks off in a group that already has runs, we want
the LLM to see what came before — prior user inputs, prior assistant
responses, prior tool-call results — instead of starting fresh from
just system + developer + the current instruction.

Composes existing black-box tools (no inline SQL):
  search_runs(group_ids)  → run_ids in this group
  search_messages(run_ids) → messages on those runs
  search_text_uploads     → text_id → upload_id
  get_upload              → upload_id → file_path
  search_calls(run_ids)   → call metadata for assistant tool_calls

Returns a flat, chronologically-ordered list of HistoryMessage records.
The caller (render_history) decides how each maps to LLM input shape
(plain text vs. OpenAI tool_calls format) based on the dispatched
agent's input modalities.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg

from app.infra.globals import UPLOAD_FOLDER, get_redis_client
from app.registry.operations import is_write_operation
from app.tools.entries.calls.search import search_calls
from app.tools.entries.messages.search import search_messages
from app.tools.entries.runs.search import search_runs
from app.tools.entries.text_uploads.search import search_text_uploads
from app.tools.entries.uploads.get import get_upload
from app.tools.resources.permissions.get import get_permissions
from app.tools.resources.tools.get import get_tools
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

# Hard cap on history messages threaded into context. Tunable; v1 is
# generous enough for normal chat flows but small enough to stay under
# typical 8K-context budgets even with verbose tool outputs.
DEFAULT_HISTORY_LIMIT = 50

# Per-message text truncation. Long tool outputs (bulk exports,
# large dumps) would otherwise blow the context. The Jinja-rendered
# template text is the load-bearing signal — past 4KB it rarely adds
# new information for the model.
PER_MESSAGE_TEXT_CAP = 4096
_TRUNCATION_SUFFIX = "\n\n[...truncated]"


@dataclass(frozen=True)
class HistoryToolCall:
    """OpenAI tool_calls payload for one assistant-attributed call."""

    call_id: UUID
    tool_id: UUID | None
    arguments: dict[str, Any]


@dataclass(frozen=True)
class HistoryMessage:
    """One persisted message in chronological history.

    For user messages: ``text`` is what the user typed OR the rendered
    Jinja text from a user-driven audited operation. ``tool_calls`` is
    always empty for user (OpenAI schema disallows tool_calls on user).

    For assistant messages: ``text`` is the assistant's response (or
    the rendered Jinja text for tool-call results). ``tool_calls`` is
    populated when the message came from an audited tool invocation —
    callers can choose to render it as the OpenAI tool_calls format
    (when the agent has ``call`` in input_modalities) or fall back to
    the plain text (when it doesn't).
    """

    role: str
    text: str
    tool_calls: list[HistoryToolCall]


async def classify_tools_read_or_write(
    conn: asyncpg.Connection,
    tool_ids: list[UUID],
) -> dict[UUID, bool]:
    """Return ``{tool_id: is_write}`` for the given tools.

    A tool is "write" if ANY of its permissions has an operation in the
    canonical ``WRITE_OPERATIONS`` registry. Two batched cached lookups
    (``get_tools`` → ``get_permissions``); sub-ms on warm cache. Tools
    not in the result map default to "treat as write" at the call site —
    we'd rather over-include possibly-mutating context than silently drop.
    """
    if not tool_ids:
        return {}
    redis = get_redis_client()
    tools_by_id = await get_tools(conn, tool_ids, redis)
    perm_ids = list({
        pid for t in tools_by_id for pid in (t.permission_ids or [])
    })
    perms = await get_permissions(conn, perm_ids, redis) if perm_ids else []
    write_op_by_perm: dict[UUID, bool] = {
        p.id: is_write_operation(p.operation or "") for p in perms
    }
    return {
        t.id: any(
            write_op_by_perm.get(pid, False)
            for pid in (t.permission_ids or [])
        )
        for t in tools_by_id
    }


def annotate_audit_only(
    per_item: list[tuple[bool, bool]],
) -> list[tuple[bool, str]]:
    """Drop "user audit" events that have no LLM-callable tool.

    Each tuple is ``(has_real_tool, has_any_calls)``:
      - ``has_real_tool``: at least one call on the message has a
        registered ``tool_id`` (i.e., something the LLM could itself
        invoke — the rendered output is reproducible context).
      - ``has_any_calls``: the message has at least one call_id.

    Items with calls but no real tool are user-driven audit events
    (file/text/audio/image downloads triggered from the UI). Their
    text_ids upload contains the auto-generated INPUT/OUTPUT body for
    the audit row, NOT a typed user instruction — so we can't use
    ``text_ids`` as a "this is real user content" signal here. Plain
    text messages have no ``call_ids`` at all and are never matched
    by this filter.

    Reasons:
      - ``"kept"``           — included
      - ``"no_tool_audit"``  — call(s) with no registered tool
    """
    out: list[tuple[bool, str]] = []
    for has_real_tool, has_any_calls in per_item:
        if has_any_calls and not has_real_tool:
            out.append((False, "no_tool_audit"))
        else:
            out.append((True, "kept"))
    return out


def combine_keep_reasons(
    *per_item_lists: list[tuple[bool, str]],
) -> list[tuple[bool, str]]:
    """Combine parallel ``(keep, reason)`` lists.

    Drop if ANY input drops; surface the first non-``kept`` reason.
    Empty input → empty output.
    """
    if not per_item_lists:
        return []
    n = len(per_item_lists[0])
    out: list[tuple[bool, str]] = []
    for i in range(n):
        keep = True
        reason = "kept"
        for lst in per_item_lists:
            k, r = lst[i]
            if not k:
                keep = False
                reason = r
                break
        out.append((keep, reason))
    return out


def annotate_read_dedup(
    tool_ids_per_item: list[set[UUID]],
    is_write_by_tool: dict[UUID, bool],
) -> list[tuple[bool, str]]:
    """For a chronological (asc) list of items, return per-item ``(keep, reason)``.

    Walks reverse-chronological. Plain items (no tool_ids) always keep —
    chat continuity. Items whose ANY referenced tool is write keep —
    every state change matters. Read-only items dedup per ``tool_id``:
    only the latest call to a given read-only tool survives, since older
    read snapshots are stale relative to the freshest.

    Default for unknown tools is ``is_write=True`` at the call site,
    so an unknown tool never gets deduped.

    Reason values:
      - ``"kept"``         — included
      - ``"deduped_read"`` — same read-only tool had a later call
    """
    seen_read_tool_ids: set[UUID] = set()
    out: list[tuple[bool, str]] = [(True, "kept")] * len(tool_ids_per_item)
    for i in range(len(tool_ids_per_item) - 1, -1, -1):
        tool_ids_here = tool_ids_per_item[i]
        if not tool_ids_here:
            continue
        if any(is_write_by_tool.get(tid, True) for tid in tool_ids_here):
            continue
        if tool_ids_here & seen_read_tool_ids:
            out[i] = (False, "deduped_read")
        else:
            seen_read_tool_ids.update(tool_ids_here)
    return out


def _truncate(text: str) -> str:
    if len(text) <= PER_MESSAGE_TEXT_CAP:
        return text
    return text[: PER_MESSAGE_TEXT_CAP - len(_TRUNCATION_SUFFIX)] + _TRUNCATION_SUFFIX


async def _read_text_for_message(
    conn: asyncpg.Connection,
    text_ids: list[UUID],
) -> str:
    """Resolve a message's text_ids to concatenated file content."""
    redis = get_redis_client()
    if not text_ids:
        return ""
    parts: list[str] = []
    junctions = await search_text_uploads(conn, redis, text_ids=text_ids, limit=len(text_ids))
    # text_uploads search returns DESC by created_at — keep one row per
    # text_id (the most recent active link).
    seen: set[UUID] = set()
    for j in junctions:
        if j.text_id in seen:
            continue
        seen.add(j.text_id)
        upload = await get_upload(conn, j.upload_id, redis)
        if upload is None:
            continue
        full_path = os.path.join(UPLOAD_FOLDER, upload.file_path)
        try:
            with open(full_path, encoding="utf-8") as fp:
                parts.append(fp.read())
        except (OSError, UnicodeDecodeError):
            # Missing or non-text upload — skip silently. Better an
            # incomplete history slice than a failed generation.
            continue
    return _truncate("\n".join(p for p in parts if p))


async def _load_call_data(
    upload_file_path: str,
) -> dict[str, Any] | None:
    """Read a calls_entry upload JSON. Returns the parsed dict or None."""
    try:
        full = os.path.join(UPLOAD_FOLDER, upload_file_path)
        with open(full, encoding="utf-8") as fp:
            data = json.load(fp)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _call_arguments(call_data: dict[str, Any] | None) -> dict[str, Any]:
    """Extract the ``arguments`` dict from a call's parsed JSON."""
    if not call_data:
        return {}
    args = call_data.get("arguments")
    return args if isinstance(args, dict) else {}


def _call_output(call_data: dict[str, Any] | None) -> str:
    """Extract the ``output`` field from a call's parsed JSON.

    This is the Jinja-rendered template result (e.g. "### Group Resolved
    ..."), without the surrounding INPUT/OUTPUT wrapper that
    ``create_tool_call`` writes into the message text body. Cleaner for
    LLM context: same content, fewer scaffold tokens, and the rendered
    output already echoes whichever arguments are significant.
    """
    if not call_data:
        return ""
    out = call_data.get("output")
    return _truncate(str(out)) if out else ""


async def fetch_group_history(
    pool: asyncpg.Pool,
    *,
    group_id: UUID,
    exclude_run_id: UUID | None = None,
    agent_id: UUID | None = None,
    limit: int = DEFAULT_HISTORY_LIMIT,
) -> list[HistoryMessage]:
    """Return up to ``limit`` recent messages in ``group_id``, oldest-first.

    The current generation's own run (when known) is excluded so that
    a freshly-persisted "user instruction" doesn't get double-counted
    once it's also appended via ``payload.instructions``.

    When ``agent_id`` is supplied, only runs whose ``agent_ids`` include
    that agent contribute history. Each agent in a multi-agent group
    has its own role, framing, and tool surface — feeding another
    agent's system/developer prompts and tool calls back as assistant
    text confuses the model and can flip its persona mid-stream. Scope
    history per dispatching agent so each LLM call sees only its own
    prior turns.
    """
    redis = get_redis_client()
    async with pool.acquire() as conn:
        # 1. Runs in the group, oldest-first. Cap the run window so we
        # don't pull thousands of rows for long-lived groups; 50 runs
        # is plenty (we cap the message slice below anyway).
        runs, _ = await search_runs(
            conn, redis,
            group_ids=[group_id],
            sort_order="asc",
            limit=50,
        )
        run_ids = [
            r.run_id
            for r in runs
            if r.run_id != exclude_run_id
            and (agent_id is None or (r.agent_ids and agent_id in r.agent_ids))
        ]
        if not run_ids:
            return []

        # 2. Messages on those runs, oldest-first. Pull more than the
        # final cap to give the per-message filter room (we drop empty
        # ones below) without recursing.
        messages, _ = await search_messages(
            conn, redis,
            run_ids=run_ids,
            sort_order="asc",
            limit=limit * 2,
        )

        # 3. Calls on those runs — indexed by call_id for cheap join below.
        calls = await search_calls(
            conn, get_redis_client(), run_ids=run_ids, limit=limit * 2,
        )
        calls_by_id: dict[UUID, Any] = {c.id: c for c in calls}

        # 4. For each message, prefer the call json's `output` field
        # (cleanly rendered template, no INPUT/OUTPUT wrapper) when
        # the message is tied to an audited call. Plain text messages
        # (assistant chat replies, system/developer framing) keep
        # using the message's text upload. Sequential reads for now —
        # 50 messages × small reads is fine.
        # We collect audit-signal triples in lockstep so the annotation
        # pass below is perfectly aligned to ``history`` without a
        # fragile replay over ``messages``.
        history: list[HistoryMessage] = []
        audit_per_item: list[tuple[bool, bool]] = []
        for m in messages:
            tool_calls: list[HistoryToolCall] = []
            text_from_call: str = ""
            real_tool_present = False
            for cid in (m.call_ids or []):
                call = calls_by_id.get(cid)
                if call is None:
                    continue
                call_data = await _load_call_data(call.file_path)
                tool_calls.append(
                    HistoryToolCall(
                        call_id=cid,
                        tool_id=call.tool_id,
                        arguments=_call_arguments(call_data),
                    )
                )
                if call.tool_id is not None:
                    real_tool_present = True
                # First call wins as the message body. In our model
                # there's typically one call per message; multi-call
                # messages are rare and can revisit if needed.
                if not text_from_call:
                    text_from_call = _call_output(call_data)

            text = text_from_call
            if not text:
                # Fallback for plain text messages (no call) and the
                # rare case where the call json went missing — read
                # the message's text upload directly.
                text = await _read_text_for_message(
                    conn, list(m.text_ids or [])
                )

            # Skip messages with no useful content at all.
            if not text and not tool_calls:
                continue
            history.append(
                HistoryMessage(
                    role=m.role or "user",
                    text=text,
                    tool_calls=tool_calls,
                )
            )
            audit_per_item.append((real_tool_present, bool(tool_calls)))

        # 5. Two parallel annotation passes:
        #   - audit-only events (calls with no registered tool, no user
        #     text) → drop; the LLM has no tool definition for them and
        #     the rendered output is just UI noise.
        #   - read-only tool dedup (latest-wins per tool_id).
        # Shared helpers so the group resolve endpoint can annotate the
        # client view the same way.
        tool_ids_per_item = [
            {tc.tool_id for tc in h.tool_calls if tc.tool_id is not None}
            for h in history
        ]
        all_tool_ids = list({tid for s in tool_ids_per_item for tid in s})
        is_write_by_tool = await classify_tools_read_or_write(conn, all_tool_ids)

        audit_anns = annotate_audit_only(audit_per_item)
        dedup_anns = annotate_read_dedup(tool_ids_per_item, is_write_by_tool)
        annotations = combine_keep_reasons(audit_anns, dedup_anns)
        history = [h for h, (keep, _reason) in zip(history, annotations) if keep]

        # 7. Trim to the last `limit` entries (newest-tailing slice,
        # but preserved chronological order).
        if len(history) > limit:
            history = history[-limit:]
        return history
