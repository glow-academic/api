"""Test get — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.test.types import GetTestResponse
from app.utils.cache.hedged_row import read_back_row

MV_NAME = "test_mv"


async def get_tests(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    *,
    bypass_cache: bool = False,
) -> list[GetTestResponse]:
    """Fetch test entries by IDs from the MV (with cache hedge)."""
    if not ids:
        return []

    cached_results: dict[str, GetTestResponse] = {}
    missing_ids: list[UUID] = []
    if not bypass_cache:
        for rid in ids:
            cached = await read_back_row(redis, "test", rid)
            if cached is not None:
                cached_results[str(rid)] = GetTestResponse.model_validate(cached)
            else:
                missing_ids.append(rid)
    else:
        missing_ids = list(ids)

    mv_results: dict[str, GetTestResponse] = {}
    if missing_ids:
        rows = await conn.fetch(
            f"""
            SELECT
                test_id, call_id, eval_id, profile_id, department_ids,
                test_name, test_description,
                num_invocations, infinite_mode, is_dynamic, archived, test_created_at
            FROM {MV_NAME}
            WHERE test_id = ANY($1)
            """,
            missing_ids,
        )
        for r in rows:
            mv_results[str(r["test_id"])] = GetTestResponse(
                test_id=r["test_id"],
                call_id=r["call_id"],
                eval_id=r["eval_id"],
                profile_id=r["profile_id"],
                department_ids=r["department_ids"],
                test_name=r["test_name"],
                test_description=r["test_description"],
                num_invocations=r["num_invocations"],
                infinite_mode=r["infinite_mode"],
                is_dynamic=r["is_dynamic"],
                archived=r["archived"],
                test_created_at=r["test_created_at"],
            )

    out: list[GetTestResponse] = []
    for rid in ids:
        key = str(rid)
        if key in cached_results:
            out.append(cached_results[key])
        elif key in mv_results:
            out.append(mv_results[key])
    return out
