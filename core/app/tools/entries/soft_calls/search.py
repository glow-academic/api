"""Soft calls SEARCH — hedged read: recent-writes cache ∪ soft_calls_mv.

Two reads run in parallel, results merged with cache winning on call_id
conflict. Bounds:
  - Cache: ZREVRANGE recent-writes set (capped at ~1000), then MGET each
    row by call_id. Catches writes the MV hasn't refreshed yet.
  - MV: same SQL as before. Catches the full history.

Merge: deduplicate by call_id (cache wins, since it has the latest
status row from append-only writes), sort by created_at DESC, apply
LIMIT/OFFSET in Python. For typical page sizes (~100) this is cheap.

Callers that explicitly want to bypass the cache merge (e.g., for
debugging stale-cache hypothesis) pass ``bypass_cache=True``.
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.soft_calls.types import GetSoftCallResponse

MV_NAME = "soft_calls_mv"
_RECENT_KEY = "entry:soft_call:recent"


def _row_key(call_id: str) -> str:
    return f"entry:soft_call:{call_id}"


def _matches_filters(
    row: dict[str, Any],
    *,
    artifact: str | None,
    artifact_ids: list[str] | None,
    operation: str | None,
    status: str | None,
    call_ids: list[str] | None,
) -> bool:
    if artifact is not None and row.get("artifact") != artifact:
        return False
    if artifact_ids is not None and row.get("artifact_id") not in artifact_ids:
        return False
    if operation is not None and row.get("operation") != operation:
        return False
    if status is not None and row.get("status") != status:
        return False
    if call_ids is not None and row.get("call_id") not in call_ids:
        return False
    return True


async def _fetch_cached_matches(
    redis: Redis,
    *,
    artifact: str | None,
    artifact_ids: list[UUID] | None,
    operation: str | None,
    status: str | None,
    call_ids: list[UUID] | None,
) -> list[dict[str, Any]]:
    """ZREVRANGE recent + MGET rows + filter. Empty list on any error."""
    recent_ids_raw = await redis.zrevrange(_RECENT_KEY, 0, -1)
    if not recent_ids_raw:
        return []

    recent_ids = [
        rid.decode() if isinstance(rid, bytes) else rid for rid in recent_ids_raw
    ]
    raws = await redis.mget(*[_row_key(rid) for rid in recent_ids])

    artifact_ids_str = [str(i) for i in artifact_ids] if artifact_ids else None
    call_ids_str = [str(i) for i in call_ids] if call_ids else None

    out: list[dict[str, Any]] = []
    for raw in raws:
        if raw is None:
            continue  # row expired or evicted; recent-set entry stale
        if isinstance(raw, bytes):
            raw = raw.decode()
        row = json.loads(raw)
        if _matches_filters(
            row,
            artifact=artifact,
            artifact_ids=artifact_ids_str,
            operation=operation,
            status=status,
            call_ids=call_ids_str,
        ):
            out.append(row)
    return out


async def search_soft_calls(
    conn: asyncpg.Connection,
    redis: Redis,
    *,
    artifact: str | None = None,
    artifact_ids: list[UUID] | None = None,
    operation: str | None = None,
    status: str | None = None,
    call_ids: list[UUID] | None = None,
    limit: int = 100,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
    include_eval: bool = False,
) -> list[GetSoftCallResponse]:
    """Hedged search: cache ∪ MV, dedupe by call_id, cache wins.

    ``include_eval`` defaults to False so the user's normal UI surfaces
    (artifact list responses' ``pending_*`` fields, the chat-panel
    ledger panel, etc.) never see dormant eval-run writes as if they
    were actionable pending state. Eval-aware tools (e.g. a benchmark
    inspector) can pass ``include_eval=True`` to surface them.
    """
    # 1. Cache half of the hedge — recent writes matching the filter.
    cached_matches: list[dict[str, Any]] = []
    if not bypass_cache:
        try:
            cached_matches = await _fetch_cached_matches(
                redis,
                artifact=artifact,
                artifact_ids=artifact_ids,
                operation=operation,
                status=status,
                call_ids=call_ids,
            )
        except Exception:
            # Hedge falls back to MV-only on Redis failure.
            cached_matches = []
    if not include_eval:
        cached_matches = [r for r in cached_matches if not r.get("eval", False)]
    cached_call_ids = {str(r["call_id"]) for r in cached_matches}

    # 2. MV half — same SQL as pre-cache implementation. Fetch enough to
    # cover offset+limit even after we dedupe; cheaper than counting.
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    mv_fetch_limit = limit + offset + len(cached_matches)

    rows = await conn.fetch(
        f"""
        SELECT soft_call_entry_id, call_id, artifact, operation,
               status, artifact_id, patch, eval, created_at
        FROM {source}
        WHERE ($1::text     IS NULL OR artifact    = $1)
          AND ($2::uuid[]   IS NULL OR artifact_id = ANY($2))
          AND ($3::text     IS NULL OR operation   = $3)
          AND ($4::text     IS NULL OR status      = $4)
          AND ($5::uuid[]   IS NULL OR call_id     = ANY($5))
          AND ($7::boolean OR eval = false)
        ORDER BY created_at DESC
        LIMIT $6
        """,
        artifact,
        artifact_ids,
        operation,
        status,
        call_ids,
        mv_fetch_limit,
        include_eval,
    )

    mv_matches: list[dict[str, Any]] = []
    for r in rows:
        if str(r["call_id"]) in cached_call_ids:
            continue  # cache has fresher version
        raw_patch = r["patch"]
        patch = json.loads(raw_patch) if isinstance(raw_patch, str) else raw_patch
        mv_matches.append({
            "id": r["soft_call_entry_id"],
            "call_id": r["call_id"],
            "artifact": r["artifact"],
            "operation": r["operation"],
            "status": r["status"],
            "artifact_id": r["artifact_id"],
            "eval": r["eval"],
            "patch": patch,
            "created_at": r["created_at"],
        })

    # 3. Merge + sort by created_at DESC. created_at may be a datetime (MV
    # path) or an ISO string (cache path); normalize for the sort key.
    def _sort_key(row: dict[str, Any]) -> datetime:
        ts = row["created_at"]
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    combined = cached_matches + mv_matches
    combined.sort(key=_sort_key, reverse=True)

    page = combined[offset : offset + limit]
    return [GetSoftCallResponse.model_validate(row) for row in page]
