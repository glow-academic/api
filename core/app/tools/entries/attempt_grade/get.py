"""Entry get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.attempt_grade.types import GetAttemptGradeResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "attempt_grade_mv"


async def get_attempt_grades(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetAttemptGradeResponse]:
    """Fetch attempt grades by grade IDs (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetAttemptGradeResponse] = {}
    missing_ids: list[UUID] = list(ids)
    if not bypass_cache:
        missing_ids = []
        for cid in ids:
            cached = await read_back_row(redis, "attempt_grade", cid)
            if cached is not None:
                payload = {k: v for k, v in cached.items() if k != "id"}
                cached_results[str(cid)] = GetAttemptGradeResponse.model_validate(payload)
            else:
                missing_ids.append(cid)

    mv_results: dict[str, GetAttemptGradeResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"SELECT * FROM {MV_NAME} WHERE grade_id = ANY($1)", missing_ids
        )
        for r in rows:
            mv_results[str(r["grade_id"])] = GetAttemptGradeResponse(**dict(r))

    out: list[GetAttemptGradeResponse] = []
    for cid in ids:
        key = str(cid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
