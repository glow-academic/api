"""Attempt grade search — filtered/paginated query against attempt_grade_mv."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.attempt_grade.types import GetAttemptGradeResponse
from app.utils.cache.hedged_row import hedged_search

MV_NAME = "attempt_grade_mv"


async def search_attempt_grades(
    conn: asyncpg.Connection,
    redis: Redis,
    chat_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> list[GetAttemptGradeResponse]:
    """Search attempt_grade entries from attempt_grade_mv with declarative filters."""
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    rows = await conn.fetch(
        f"""
        SELECT grade_id, chat_id, score, passed, time_taken, total_points,
               pass_points, rubric_id, created_at
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR chat_id = ANY($1))
          AND ($2::uuid[] IS NULL OR rubric_id = ANY($2))
        ORDER BY created_at DESC
        LIMIT $3 OFFSET $4
        """,
        chat_ids,
        rubric_ids,
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "grade_id": str(r["grade_id"]),
            "chat_id": str(r["chat_id"]),
            "score": float(r["score"]) if r["score"] is not None else 0.0,
            "passed": r["passed"],
            "time_taken": r["time_taken"],
            "total_points": r["total_points"],
            "pass_points": r["pass_points"],
            "rubric_id": str(r["rubric_id"]) if r["rubric_id"] else None,
            "created_at": r["created_at"],
            # Synthetic ``id`` so hedged_search default id_key works.
            "id": str(r["grade_id"]),
        }
        for r in rows
    ]

    chat_ids_str = {str(c) for c in chat_ids} if chat_ids else None
    rubric_ids_str = {str(r) for r in rubric_ids} if rubric_ids else None

    def matches(row: dict) -> bool:
        if chat_ids_str is not None and str(row.get("chat_id")) not in chat_ids_str:
            return False
        if rubric_ids_str is not None:
            v = row.get("rubric_id")
            if v is None or str(v) not in rubric_ids_str:
                return False
        return True

    merged = await hedged_search(
        redis,
        "attempt_grade",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [
        GetAttemptGradeResponse.model_validate(
            {k: v for k, v in r.items() if k != "id"}
        )
        for r in merged
    ]
