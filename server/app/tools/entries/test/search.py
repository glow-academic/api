"""Test search — filtered/paginated query against test_mv."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test.types import GetTestResponse

MV_NAME = "test_mv"


async def search_tests(
    conn: asyncpg.Connection,
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
) -> tuple[list[GetTestResponse], int]:
    """Search test entries from test_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    order = "ASC" if sort_order.lower() == "asc" else "DESC"

    rows = await conn.fetch(
        f"""
        SELECT test_id, eval_id, profile_id, department_ids,
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
        ORDER BY test_created_at {order}
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
