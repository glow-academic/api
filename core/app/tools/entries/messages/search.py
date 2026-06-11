"""Messages search — filtered/paginated query against messages_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.messages.types import SearchMessageResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "messages_mv"


async def search_messages(
    conn: asyncpg.Connection,
    redis: Redis,
    run_ids: list[UUID] | None = None,
    role: str | None = None,
    roles: list[str] | None = None,
    agent_ids: list[UUID] | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[SearchMessageResponse], int]:
    """Search messages from messages_mv with declarative filters.

    Hedged: merges the MV result with the write-back cache (see
    ``hedged_search_with_total``) so freshly-created messages appear before
    the MV refresh has caught up.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)
    source_alias = "mv" if bypass_mv else "m"
    from_source = source if bypass_mv else f"{source} {source_alias}"

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    # The agent filter uses an EXISTS subquery rather than a LEFT JOIN so a
    # message linked to N agents stays a single row. A join would fan it out,
    # and ``COUNT(*) OVER()`` (evaluated before ``DISTINCT``) would then
    # over-count the unpaginated total — corrupting the "Showing X of Y" UI.
    rows = await conn.fetch(
        f"""
        SELECT {source_alias}.message_id, {source_alias}.run_id, {source_alias}.role, {source_alias}.message_created_at,
               {source_alias}.text_ids, {source_alias}.audio_ids, {source_alias}.image_ids,
               {source_alias}.video_ids, {source_alias}.file_ids, {source_alias}.call_ids,
               {source_alias}.reasoning,
               COUNT(*) OVER() AS total_count
        FROM {from_source}
        WHERE ($1::uuid[] IS NULL OR {source_alias}.run_id = ANY($1))
          AND ($2::text IS NULL OR {source_alias}.role = $2)
          AND ($3::uuid[] IS NULL OR EXISTS (
                SELECT 1 FROM messages_agents_connection mac
                WHERE mac.message_id = {source_alias}.message_id
                  AND mac.agents_id = ANY($3)
          ))
          AND ($4::text[] IS NULL OR {source_alias}.role = ANY($4))
        ORDER BY {source_alias}.message_created_at {order},
                 {source_alias}.reasoning DESC,
                 {source_alias}.message_id {order}
        LIMIT $5 OFFSET $6
        """,
        run_ids,
        role,
        agent_ids,
        roles,
        limit + offset + 1000,
        0,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    # Reshape MV rows to match the cache-row keyspace (str ids, isoformat
    # timestamps) so the merged dicts dedupe & sort consistently.
    mv_dicts = [
        {
            "message_id": str(r["message_id"]),
            "run_id": str(r["run_id"]) if r["run_id"] else None,
            "role": r["role"],
            "message_created_at": (
                r["message_created_at"].isoformat()
                if isinstance(r["message_created_at"], datetime)
                else r["message_created_at"]
            ),
            "text_ids": [str(x) for x in (r["text_ids"] or [])],
            "audio_ids": [str(x) for x in (r["audio_ids"] or [])],
            "image_ids": [str(x) for x in (r["image_ids"] or [])],
            "video_ids": [str(x) for x in (r["video_ids"] or [])],
            "file_ids": [str(x) for x in (r["file_ids"] or [])],
            "call_ids": [str(x) for x in (r["call_ids"] or [])],
            "reasoning": r["reasoning"],
        }
        for r in rows
    ]

    run_ids_str = {str(x) for x in run_ids} if run_ids else None
    roles_set = set(roles) if roles else None
    agent_ids_str = {str(x) for x in agent_ids} if agent_ids else None

    def matches(row: dict) -> bool:
        if run_ids_str is not None and str(row.get("run_id")) not in run_ids_str:
            return False
        if role is not None and row.get("role") != role:
            return False
        if roles_set is not None and row.get("role") not in roles_set:
            return False
        if agent_ids_str is not None:
            row_agents = {str(a) for a in (row.get("agent_ids") or [])}
            if not (row_agents & agent_ids_str):
                return False
        return True

    def _ts(row: dict) -> datetime:
        ts = row.get("message_created_at")
        if ts is None:
            return datetime.min
        if isinstance(ts, str):
            return datetime.fromisoformat(ts)
        return ts

    # Deterministic ordering (H3). A reasoning trace and its answer for the
    # same turn can land at the SAME ``message_created_at`` (the reasoning
    # row's back-dated ``reasoning_started_at`` is None when reasoning
    # arrived without a prior delta, so both stamp run-complete "now" in the
    # same transaction). With only a timestamp sort the two rows tie and can
    # replay in either order — reasoning AFTER the answer. Break the tie so
    # reasoning consistently precedes the answer (reasoning row first), then
    # by ``message_id`` for a fully stable order. This mirrors the SQL
    # ``ORDER BY message_created_at <ord>, reasoning DESC, message_id <ord>``
    # above. The ASC key is applied directly; the DESC key is built so the
    # hedge helper's internal ``reverse=True`` reproduces the same SQL order
    # (reasoning row first, message_id DESC on the tie).
    def _sort_key_asc(row: dict) -> tuple[datetime, bool, str]:
        return (_ts(row), not bool(row.get("reasoning")), str(row.get("message_id") or ""))

    def _sort_key_desc(row: dict) -> tuple[datetime, bool, str]:
        return (_ts(row), bool(row.get("reasoning")), str(row.get("message_id") or ""))

    # ``hedged_search_with_total`` sorts DESC + paginates internally.
    # For ASC requests we fall back to MV-only (helper has no ASC mode);
    # in practice all hot callers use DESC.
    if sort_order.lower() == "asc":
        mv_dicts.sort(key=_sort_key_asc)
        items_list = mv_dicts[offset : offset + limit]
        return [SearchMessageResponse.model_validate(r) for r in items_list], mv_total

    items, total = await hedged_search_with_total(
        redis,
        "messages",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key_desc,
        limit=limit,
        offset=offset,
        id_key="message_id",
        bypass_cache=bypass_cache,
    )

    return [SearchMessageResponse.model_validate(r) for r in items], total
