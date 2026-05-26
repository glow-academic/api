"""Test search — filtered/paginated query against test_mv."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test.types import GetTestResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "test_mv"


async def search_tests(
    conn: asyncpg.Connection,
    redis: Redis,
    test_ids: list[UUID] | None = None,
    eval_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    is_archived: bool | None = None,
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[GetTestResponse], int]:
    """Search test entries from test_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    # For ASC, recent cache writes won't affect the visible page (they're at
    # the tail), so skip the hedge and use the MV directly. For DESC, pad the
    # fetch so dedupe against the cache merge still leaves enough rows to
    # satisfy offset+limit.
    if order == "ASC":
        rows = await conn.fetch(
            f"""
            SELECT test_id, call_id, eval_id, profile_id, department_ids,
                   test_name, test_description,
                   num_invocations, infinite_mode, is_dynamic, archived, test_created_at,
                   COUNT(*) OVER() AS total_count
            FROM {source}
            WHERE ($1::uuid[] IS NULL OR test_id = ANY($1))
              AND ($2::uuid[] IS NULL OR eval_id = ANY($2))
              AND ($3::uuid[] IS NULL OR profile_id = ANY($3))
              AND ($4::uuid[] IS NULL OR department_ids && $4)
              AND ($5::timestamptz IS NULL OR test_created_at >= $5)
              AND ($6::timestamptz IS NULL OR test_created_at <= $6)
              AND ($7::bool IS NULL OR archived = $7)
            ORDER BY test_created_at ASC
            LIMIT $8 OFFSET $9
            """,
            test_ids,
            eval_ids,
            profile_ids,
            department_ids,
            date_from,
            date_to,
            is_archived,
            limit,
            offset,
        )
        total_count = rows[0]["total_count"] if rows else 0
        items = [
            GetTestResponse(**{k: v for k, v in dict(r).items() if k != "total_count"})
            for r in rows
        ]
        return (items, total_count)

    rows = await conn.fetch(
        f"""
        SELECT test_id, call_id, eval_id, profile_id, department_ids,
               test_name, test_description,
               num_invocations, infinite_mode, is_dynamic, archived, test_created_at,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR test_id = ANY($1))
          AND ($2::uuid[] IS NULL OR eval_id = ANY($2))
          AND ($3::uuid[] IS NULL OR profile_id = ANY($3))
          AND ($4::uuid[] IS NULL OR department_ids && $4)
          AND ($5::timestamptz IS NULL OR test_created_at >= $5)
          AND ($6::timestamptz IS NULL OR test_created_at <= $6)
          AND ($7::bool IS NULL OR archived = $7)
        ORDER BY test_created_at DESC
        LIMIT $8 OFFSET $9
        """,
        test_ids,
        eval_ids,
        profile_ids,
        department_ids,
        date_from,
        date_to,
        is_archived,
        limit + offset + 1000,
        0,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    mv_dicts = [
        {k: v for k, v in dict(r).items() if k != "total_count"} for r in rows
    ]

    test_ids_str = {str(x) for x in test_ids} if test_ids else None
    eval_ids_str = {str(x) for x in eval_ids} if eval_ids else None
    profile_ids_str = {str(x) for x in profile_ids} if profile_ids else None
    department_ids_str = (
        {str(x) for x in department_ids} if department_ids else None
    )

    def _parse_ts(ts: datetime | str | None) -> datetime | None:
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    def matches(row: dict) -> bool:
        if test_ids_str is not None and str(row.get("test_id")) not in test_ids_str:
            return False
        if eval_ids_str is not None and str(row.get("eval_id")) not in eval_ids_str:
            return False
        if (
            profile_ids_str is not None
            and str(row.get("profile_id")) not in profile_ids_str
        ):
            return False
        if department_ids_str is not None:
            row_depts = {str(d) for d in (row.get("department_ids") or [])}
            if not (row_depts & department_ids_str):
                return False
        ts = _parse_ts(row.get("test_created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if is_archived is not None and row.get("archived") != is_archived:
            return False
        return True

    def _sort_key(row: dict) -> datetime:
        ts = row.get("test_created_at")
        if ts is None:
            return _dt.min
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    items, total = await hedged_search_with_total(
        redis,
        "test",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        id_key="test_id",
        bypass_cache=bypass_cache,
    )

    return (
        [GetTestResponse.model_validate(r) for r in items],
        total,
    )
