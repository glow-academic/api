"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.test_grade.types import GetTestGradeResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "test_grade_mv"


async def get_test_grades(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetTestGradeResponse]:
    """Fetch test grades by IDs (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTestGradeResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "test_grade", rid)
            if cached is not None:
                cached_results[str(rid)] = GetTestGradeResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTestGradeResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE id = ANY($1)", missing_ids,
        )
        for r in rows:
            mv_results[str(r["id"])] = GetTestGradeResponse(**dict(r))

    out: list[GetTestGradeResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
