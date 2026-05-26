"""Test invocation search — filtered/paginated query against test_invocation_mv."""

from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_invocation.types import GetTestInvocationResponse
from app.utils.cache.hedged_row import hedged_search_with_total

MV_NAME = "test_invocation_mv"


async def search_test_invocation_entries_internal(
    conn: asyncpg.Connection,
    redis: Redis,
    test_ids: list[UUID] | None = None,
    group_ids: list[UUID] | None = None,
    suite_department_ids: list[UUID] | None = None,
    grade_ids: list[UUID] | None = None,
    rubric_ids: list[UUID] | None = None,
    agent_ids: list[UUID] | None = None,
    quality_ids: list[UUID] | None = None,
    voice_ids: list[UUID] | None = None,
    temperature_level_ids: list[UUID] | None = None,
    reasoning_level_ids: list[UUID] | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_mv: bool = False,
    bypass_cache: bool = False,
) -> tuple[list[GetTestInvocationResponse], int]:
    """Search test_invocation entries from test_invocation_mv with declarative filters.

    Returns (items, total_count).
    """
    source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

    # Padded fetch so dedupe against the cache merge still leaves enough rows
    # to satisfy offset+limit. COUNT(*) OVER() reflects the unpaginated total.
    rows = await conn.fetch(
        f"""
        SELECT invocation_id, test_id, group_id, invocation_created_at,
               invocation_title, use_custom, "position", invocation_completed,
               grade_id, grade_score, grade_passed, grade_time_taken,
               rubric_id, agent_ids, quality_id, department_ids, voice_id,
               temperature_level_id, reasoning_level_id, modality_ids,
               COUNT(*) OVER() AS total_count
        FROM {source}
        WHERE ($1::uuid[] IS NULL OR test_id = ANY($1))
          AND ($2::uuid[] IS NULL OR group_id = ANY($2))
          AND ($3::uuid[] IS NULL OR department_ids && $3)
          AND ($4::uuid[] IS NULL OR grade_id = ANY($4))
          AND ($5::uuid[] IS NULL OR rubric_id = ANY($5))
          AND ($6::uuid[] IS NULL OR agent_ids && $6)
          AND ($7::uuid[] IS NULL OR quality_id = ANY($7))
          AND ($8::uuid[] IS NULL OR voice_id = ANY($8))
          AND ($9::uuid[] IS NULL OR temperature_level_id = ANY($9))
          AND ($10::uuid[] IS NULL OR reasoning_level_id = ANY($10))
        ORDER BY invocation_created_at DESC
        LIMIT $11 OFFSET $12
        """,
        test_ids,
        group_ids,
        suite_department_ids,
        grade_ids,
        rubric_ids,
        agent_ids,
        quality_ids,
        voice_ids,
        temperature_level_ids,
        reasoning_level_ids,
        limit + offset + 1000,
        0,
    )

    mv_total = rows[0]["total_count"] if rows else 0

    mv_dicts = [
        {k: v for k, v in dict(r).items() if k != "total_count"} for r in rows
    ]

    test_ids_str = {str(x) for x in test_ids} if test_ids else None
    group_ids_str = {str(x) for x in group_ids} if group_ids else None
    suite_dept_str = (
        {str(x) for x in suite_department_ids} if suite_department_ids else None
    )
    grade_ids_str = {str(x) for x in grade_ids} if grade_ids else None
    rubric_ids_str = {str(x) for x in rubric_ids} if rubric_ids else None
    agent_ids_str = {str(x) for x in agent_ids} if agent_ids else None
    quality_ids_str = {str(x) for x in quality_ids} if quality_ids else None
    voice_ids_str = {str(x) for x in voice_ids} if voice_ids else None
    temp_ids_str = (
        {str(x) for x in temperature_level_ids} if temperature_level_ids else None
    )
    reason_ids_str = (
        {str(x) for x in reasoning_level_ids} if reasoning_level_ids else None
    )

    def matches(row: dict) -> bool:
        if test_ids_str is not None and str(row.get("test_id")) not in test_ids_str:
            return False
        if group_ids_str is not None and str(row.get("group_id")) not in group_ids_str:
            return False
        if suite_dept_str is not None:
            row_depts = {str(d) for d in (row.get("department_ids") or [])}
            if not (row_depts & suite_dept_str):
                return False
        if grade_ids_str is not None and str(row.get("grade_id")) not in grade_ids_str:
            return False
        if (
            rubric_ids_str is not None
            and str(row.get("rubric_id")) not in rubric_ids_str
        ):
            return False
        if agent_ids_str is not None:
            row_agents = {str(a) for a in (row.get("agent_ids") or [])}
            if not (row_agents & agent_ids_str):
                return False
        if (
            quality_ids_str is not None
            and str(row.get("quality_id")) not in quality_ids_str
        ):
            return False
        if (
            voice_ids_str is not None
            and str(row.get("voice_id")) not in voice_ids_str
        ):
            return False
        if (
            temp_ids_str is not None
            and str(row.get("temperature_level_id")) not in temp_ids_str
        ):
            return False
        if (
            reason_ids_str is not None
            and str(row.get("reasoning_level_id")) not in reason_ids_str
        ):
            return False
        return True

    def _sort_key(row: dict) -> _dt:
        ts = row.get("invocation_created_at")
        if ts is None:
            return _dt.min
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    items, total = await hedged_search_with_total(
        redis,
        "test_invocation",
        mv_rows=mv_dicts,
        mv_total=mv_total,
        matches_filter=matches,
        sort_key=_sort_key,
        limit=limit,
        offset=offset,
        id_key="invocation_id",
        bypass_cache=bypass_cache,
    )

    return (
        [GetTestInvocationResponse.model_validate(r) for r in items],
        total,
    )
