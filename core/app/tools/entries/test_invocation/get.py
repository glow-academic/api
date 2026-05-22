"""test_invocation/get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.docs.resolve_mv_source import resolve_mv_source
from app.tools.entries.test_invocation.types import (
    GetTestInvocationResponse,
)
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "test_invocation_mv"


async def get_test_invocations(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_mv: bool = False,
    *,
    bypass_cache: bool = False,
) -> list[GetTestInvocationResponse]:
    """Fetch test_invocation entries by IDs from the MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTestInvocationResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "test_invocation", rid)
            if cached is not None:
                cached_results[str(rid)] = (
                    GetTestInvocationResponse.model_validate(cached)
                )
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTestInvocationResponse] = {}
    if missing_ids:
        source = await resolve_mv_source(conn, MV_NAME, bypass_mv)

        rows = await conn.fetch(
            f"""
            SELECT
                invocation_id, test_id, group_id, invocation_created_at,
                invocation_title, use_custom, "position", invocation_completed,
                grade_id, grade_score, grade_passed, grade_time_taken,
                rubric_id, agent_ids, quality_id, department_ids, voice_id,
                temperature_level_id, reasoning_level_id, modality_ids
            FROM {source}
            WHERE invocation_id = ANY($1)
            """,
            missing_ids,
        )

        for r in rows:
            mv_results[str(r["invocation_id"])] = GetTestInvocationResponse(
                invocation_id=r["invocation_id"],
                test_id=r["test_id"],
                group_id=r["group_id"],
                invocation_created_at=r["invocation_created_at"],
                invocation_title=r["invocation_title"],
                use_custom=r["use_custom"],
                position=r["position"],
                invocation_completed=r["invocation_completed"],
                grade_id=r["grade_id"],
                grade_score=r["grade_score"],
                grade_passed=r["grade_passed"],
                grade_time_taken=r["grade_time_taken"],
                rubric_id=r["rubric_id"],
                agent_ids=r["agent_ids"],
                quality_id=r["quality_id"],
                department_ids=r["department_ids"],
                voice_id=r["voice_id"],
                temperature_level_id=r["temperature_level_id"],
                reasoning_level_id=r["reasoning_level_id"],
                modality_ids=r["modality_ids"],
            )

    out: list[GetTestInvocationResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
