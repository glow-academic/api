"""test_feedback/search — filtered/paginated query against test_feedback_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_feedback.types import GetTestFeedbackResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "test_feedback_mv"


async def search_test_feedback_entries(
    conn: asyncpg.Connection,
    redis: Redis,
    grade_ids: list[UUID] | None = None,
    tool_call_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetTestFeedbackResponse]:
    """Search test_feedback entries from test_feedback_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT feedback_id, grade_id, call_id, tool_call_id, standard_id,
               total, feedback, total_points, pass_points, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR grade_id = ANY($1))
          AND ($4::uuid[] IS NULL OR tool_call_id = ANY($4))
        ORDER BY created_at DESC
        LIMIT $2 OFFSET $3
        """,
        grade_ids,
        limit + offset + 1000,
        0,
        tool_call_ids,
    )

    mv_dicts = [
        {
            "id": f"{r['feedback_id']}:{r['standard_id'] if r['standard_id'] else 'none'}",
            "feedback_id": str(r["feedback_id"]),
            "grade_id": str(r["grade_id"]) if r["grade_id"] else None,
            "call_id": str(r["call_id"]) if r["call_id"] else None,
            "tool_call_id": str(r["tool_call_id"]) if r["tool_call_id"] else None,
            "standard_id": str(r["standard_id"]) if r["standard_id"] else None,
            "total": r["total"],
            "feedback": r["feedback"],
            "total_points": r["total_points"],
            "pass_points": r["pass_points"],
            "created_at": r["created_at"],
        }
        for r in rows
    ]

    grade_ids_str = {str(g) for g in grade_ids} if grade_ids else None
    tool_call_ids_str = {str(t) for t in tool_call_ids} if tool_call_ids else None

    def matches(row: dict) -> bool:
        if grade_ids_str is not None and str(row.get("grade_id")) not in grade_ids_str:
            return False
        if tool_call_ids_str is not None and str(row.get("tool_call_id")) not in tool_call_ids_str:
            return False
        return True

    merged = await hedged_search(
        redis,
        "test_feedback",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [
        GetTestFeedbackResponse.model_validate({k: v for k, v in r.items() if k != "id"})
        for r in merged
    ]
