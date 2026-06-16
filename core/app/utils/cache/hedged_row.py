"""Hedged-read cache helpers for entry primitives.

Generalizes the v1.0.16 soft_calls pattern into shared utilities that any
entry primitive (calls, messages, runs, sessions, etc.) can use uniformly.

The pattern:

  1. ``write_back_row`` — at INSERT time, write the freshly-created row to
     ``entry:<X>:<id>`` and ZADD to a capped ``entry:<X>:recent`` sorted set
     (one pipelined round-trip).
  2. ``read_back_row`` — at GET-by-id time, check the per-id cache first;
     fall through to the MV on miss.
  3. ``hedged_search`` — at SEARCH time, ZREVRANGE the recent set + MGET
     each cached row, filter in Python with caller-supplied predicate,
     UNION with the MV result, dedupe by id, sort + paginate. Captures
     just-written rows the MV hasn't refreshed yet.
  4. ``invalidate_row`` — for soft-delete / active-flip / junction-update
     paths that change what the GET response would return.

Why hedged: same shape as Jeff Dean's "Tail at Scale" hedged requests —
fan out two reads in parallel (cache + MV), prefer the fresher source.
Trades a tiny amount of extra Redis work for read-after-write consistency
without a sync MV REFRESH on the writer's critical path.

Memory: each entry namespace stores at most ``_RECENT_CAP`` rows in the
recent-writes index; per-id rows live for ``_TTL`` then expire. Estimate
~1MB Redis per active entry namespace, well under any reasonable budget.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

_TTL = 3600  # 1h — outlives MV refresh window; self-heals on next write
_RECENT_CAP = 1000  # bounds per-namespace memory of the merge-index

# report-19 HC2: when a write-back is issued inside a Postgres transaction, the
# Redis SETEX must NOT fire until that transaction COMMITS — otherwise a later
# statement that rolls the txn back leaves a phantom cache row served for _TTL
# with no backing DB row. ``transaction_with_writeback`` sets this ContextVar to
# a pending-queue for the duration of the (outermost) transaction; while it is
# set, ``write_back_row`` enqueues instead of writing, and the queue is flushed
# only on successful commit. None ⇒ no active deferral ⇒ write immediately
# (unchanged behaviour for write-backs outside any transaction).
_pending_writebacks: ContextVar[
    list[tuple[Redis, str, "UUID | str", dict[str, Any], "int | None"]] | None
] = ContextVar("_pending_writebacks", default=None)


def clear_writeback_deferral() -> None:
    """Reset the write-back deferral for the current context.

    report-20 V2: ``transaction_with_writeback`` keeps its pending-queue in a
    ContextVar, and ``asyncio.create_task`` COPIES the current context into the
    new task. A fire-and-forget task spawned *inside* a deferred transaction
    would therefore inherit that queue — but it runs AFTER (and outside) the
    transaction's commit/rollback, so any ``write_back_row`` it issues must fire
    immediately, not enqueue into a queue the parent already flushed/discarded
    (which would silently drop the write-back, or flush it as a phantom before
    the task's own DB write commits). Background-task spawners call this at task
    entry so the child always does immediate write-backs. Idempotent and safe to
    call when no deferral is active.
    """
    _pending_writebacks.set(None)


def _row_key(entry: str, row_id: UUID | str) -> str:
    return f"entry:{entry}:{row_id}"


def _recent_key(entry: str) -> str:
    return f"entry:{entry}:recent"


async def write_back_row(
    redis: Redis,
    entry: str,
    row_id: UUID | str,
    row: dict[str, Any],
    score_ms: int | None = None,
) -> None:
    """Cache a freshly-inserted row.

    One pipelined round-trip:
      SETEX entry:<X>:<id>        <ttl>  <json>
      ZADD  entry:<X>:recent      <score> <id>
      ZREMRANGEBYRANK             0 -<cap-1>  (cap memory)
      EXPIRE entry:<X>:recent     <ttl>

    ``score_ms`` is the row's creation timestamp in milliseconds. Defaults
    to ``time.time()*1000`` if omitted; pass the row's own ``created_at``
    for ordering consistency with the MV (which orders by ``created_at``).

    Best-effort: errors are swallowed so a cache outage doesn't break writes.

    HC2: if called inside a ``transaction_with_writeback`` block, the actual
    Redis write is DEFERRED and flushed only after the surrounding Postgres
    transaction commits (so a rollback leaves no phantom cache row).
    """
    if score_ms is None:
        import time
        score_ms = int(time.time() * 1000)
    pending = _pending_writebacks.get()
    if pending is not None:
        # Inside a deferred-write-back transaction: enqueue, flush on commit.
        pending.append((redis, entry, row_id, row, score_ms))
        return
    await _do_write_back_row(redis, entry, row_id, row, score_ms)


async def _do_write_back_row(
    redis: Redis,
    entry: str,
    row_id: UUID | str,
    row: dict[str, Any],
    score_ms: int,
) -> None:
    """Issue the actual Redis SETEX+ZADD for a write-back. Best-effort."""
    try:
        async with redis.pipeline(transaction=False) as pipe:
            pipe.setex(_row_key(entry, row_id), _TTL, json.dumps(row, default=str))
            pipe.zadd(_recent_key(entry), {str(row_id): score_ms})
            pipe.zremrangebyrank(_recent_key(entry), 0, -_RECENT_CAP - 1)
            pipe.expire(_recent_key(entry), _TTL)
            await pipe.execute()
    except Exception:
        pass


@asynccontextmanager
async def transaction_with_writeback(conn: asyncpg.Connection):
    """Drop-in replacement for ``conn.transaction()`` that defers any
    ``write_back_row`` issued inside it until AFTER the Postgres transaction
    commits — closing report-19 HC2 (write-backs surviving a rollback as phantom
    cache rows).

    Semantics:
      - Outermost use sets the pending-queue; nested uses (asyncpg SAVEPOINTs)
        simply participate — they do NOT flush, since a savepoint release is not
        a durable commit and the outer txn can still roll back. The outermost
        block owns the single flush.
      - The queue is flushed ONLY if the transaction block exits without raising
        (i.e. the COMMIT succeeded). On any exception (rollback) the queued
        write-backs are discarded — no phantom rows.

    Usage:  ``async with transaction_with_writeback(conn):  ...creates...``
    """
    outer = _pending_writebacks.get() is None
    token = _pending_writebacks.set([]) if outer else None
    committed = False
    try:
        async with conn.transaction():
            yield
        committed = True  # reached only after a successful COMMIT
    finally:
        if outer:
            pending = _pending_writebacks.get() or []
            assert token is not None
            _pending_writebacks.reset(token)
            if committed:
                for redis_c, entry_c, row_id_c, row_c, score_c in pending:
                    await _do_write_back_row(
                        redis_c, entry_c, row_id_c, row_c, score_c
                    )


async def read_back_row(
    redis: Redis, entry: str, row_id: UUID | str,
) -> dict[str, Any] | None:
    """Check the per-id write-back cache. Returns parsed dict or None on miss."""
    try:
        raw = await redis.get(_row_key(entry, row_id))
    except Exception:
        return None
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode()
    try:
        return json.loads(raw)
    except Exception:
        return None


async def read_back_rows(
    redis: Redis, entry: str, row_ids: list[UUID | str],
) -> dict[str, dict[str, Any]]:
    """Batch variant of ``read_back_row`` — one pipelined MGET for all ids.

    Returns a ``{str(id): parsed_dict}`` map containing only cache HITS;
    missing/undecodable ids are simply absent. Behaviour for any single id is
    identical to ``read_back_row`` (same key, same JSON parse), but collapses N
    per-id ``GET`` round-trips into one ``MGET`` — the same merge-index pattern
    ``hedged_search`` already uses. Best-effort: a cache outage yields ``{}``.
    """
    if not row_ids:
        return {}
    keys = [_row_key(entry, rid) for rid in row_ids]
    try:
        raws = await redis.mget(*keys)
    except Exception:
        return {}
    out: dict[str, dict[str, Any]] = {}
    for rid, raw in zip(row_ids, raws or []):
        if raw is None:
            continue
        if isinstance(raw, bytes):
            raw = raw.decode()
        try:
            out[str(rid)] = json.loads(raw)
        except Exception:
            continue
    return out


async def invalidate_row(
    redis: Redis, entry: str, row_id: UUID | str,
) -> None:
    """Bust a row's cache entry. Use on:
      - row-level UPDATEs (rare in this codebase — append-only entries)
      - junction-table writes that change what the parent entry's GET returns
        (e.g. tool_drafts_<X>_connection active-flag flips affect tool_drafts entry)
      - soft-delete flows that flip the entry's active flag
    """
    try:
        await redis.delete(_row_key(entry, row_id))
    except Exception:
        pass


async def hedged_search(
    redis: Redis,
    entry: str,
    *,
    mv_rows: list[dict[str, Any]],
    matches_filter: Callable[[dict[str, Any]], bool],
    sort_key: Callable[[dict[str, Any]], Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    id_key: str = "id",
    bypass_cache: bool = False,
) -> list[dict[str, Any]]:
    """Merge recent-writes cache with MV result.

    Steps:
      1. ZREVRANGE the recent-writes set for ``entry`` → list of recent ids
      2. MGET each cached row (pipelined). Cache misses are skipped.
      3. Filter cached rows via ``matches_filter`` (caller-supplied closure
         over the search's query params). Cached rows that pass the filter
         take precedence over MV rows with the same id (cache is fresher).
      4. UNION with ``mv_rows``, dedupe by ``id_key``.
      5. Sort by ``sort_key`` (default: created_at DESC) and paginate.

    ``matches_filter`` mirrors the SQL WHERE clauses the caller used to
    fetch ``mv_rows`` — so a recently-written row that matches the same
    search criteria is included; one that doesn't is skipped.

    Returns the merged + paginated result. ``mv_rows`` should be unsorted /
    unpaginated for correctness; this function does both at the end.
    Caller is responsible for fetching enough MV rows to cover offset+limit
    after dedupe (typically: fetch limit + len(cached_matches) rows).
    """
    if bypass_cache:
        rows = list(mv_rows)
        rows.sort(key=sort_key or _default_sort, reverse=True)
        return rows[offset : offset + limit]

    cached_matches: list[dict[str, Any]] = []
    try:
        recent_ids_raw = await redis.zrevrange(_recent_key(entry), 0, -1)
    except Exception:
        recent_ids_raw = []

    if recent_ids_raw:
        ids = [
            rid.decode() if isinstance(rid, bytes) else rid for rid in recent_ids_raw
        ]
        try:
            raws = await redis.mget(*[_row_key(entry, rid) for rid in ids])
        except Exception:
            raws = []
        for raw in raws or []:
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if matches_filter(row):
                cached_matches.append(row)

    cached_ids = {str(r.get(id_key)) for r in cached_matches}
    mv_kept = [r for r in mv_rows if str(r.get(id_key)) not in cached_ids]

    combined = cached_matches + mv_kept
    combined.sort(key=sort_key or _default_sort, reverse=True)
    return combined[offset : offset + limit]


async def hedged_search_with_total(
    redis: Redis,
    entry: str,
    *,
    mv_rows: list[dict[str, Any]],
    mv_total: int,
    matches_filter: Callable[[dict[str, Any]], bool],
    sort_key: Callable[[dict[str, Any]], Any] | None = None,
    limit: int = 100,
    offset: int = 0,
    id_key: str = "id",
    bypass_cache: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Same as ``hedged_search`` but returns ``(items, total_count)``.

    For searches whose response shape is ``tuple[list, int]`` (paginated
    UIs that surface a total like "Showing 20 of 137"). ``mv_total`` is
    the MV-side ``COUNT(*) OVER()`` for the unpaginated result; we add
    the count of cached rows that aren't already in the MV result to
    capture write-after-MV-refresh deltas.

    ``mv_rows`` is the unsorted / unpaginated MV slice (already padded
    via the standard ``LIMIT + offset + 1000`` trick); this function
    sorts + paginates the merged list internally.
    """
    if bypass_cache:
        rows = list(mv_rows)
        rows.sort(key=sort_key or _default_sort, reverse=True)
        return rows[offset : offset + limit], mv_total

    cached_matches: list[dict[str, Any]] = []
    try:
        recent_ids_raw = await redis.zrevrange(_recent_key(entry), 0, -1)
    except Exception:
        recent_ids_raw = []

    if recent_ids_raw:
        ids = [
            rid.decode() if isinstance(rid, bytes) else rid for rid in recent_ids_raw
        ]
        try:
            raws = await redis.mget(*[_row_key(entry, rid) for rid in ids])
        except Exception:
            raws = []
        for raw in raws or []:
            if raw is None:
                continue
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                row = json.loads(raw)
            except Exception:
                continue
            if matches_filter(row):
                cached_matches.append(row)

    mv_ids = {str(r.get(id_key)) for r in mv_rows}
    extra = sum(1 for c in cached_matches if str(c.get(id_key)) not in mv_ids)

    cached_ids = {str(r.get(id_key)) for r in cached_matches}
    mv_kept = [r for r in mv_rows if str(r.get(id_key)) not in cached_ids]

    combined = cached_matches + mv_kept
    combined.sort(key=sort_key or _default_sort, reverse=True)
    return combined[offset : offset + limit], mv_total + extra


def _default_sort(row: dict[str, Any]) -> datetime:
    """Default sort key: created_at. Handles both datetime and ISO str shapes
    so cache rows (serialized) and MV rows (asyncpg datetime) sort together."""
    ts = row.get("created_at")
    if ts is None:
        return datetime.min
    if isinstance(ts, str):
        return datetime.fromisoformat(ts)
    return ts
