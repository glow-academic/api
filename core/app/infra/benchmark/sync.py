"""Eval benchmark entry sync — pre-create benchmark + invocation entries on eval save.

Insert-only. No reads from _entry tables. No deactivation of old entries.
Uses black-box entry creation tools instead of raw SQL.
"""

import asyncio
from typing import Any, cast
from uuid import UUID

import asyncpg  # type: ignore

from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)


async def sync_benchmark_entries(
    pool: asyncpg.Pool,
    evals_resource_id: UUID,
    model_ids: list[UUID],
    model_flag_ids: list[UUID],
    model_rubric_ids: list[UUID],
    model_position_ids: list[UUID],
    department_ids: list[UUID],
) -> int:
    """Sync benchmark entries by pre-creating benchmark + invocation entries.

    Three-pass approach:
    1. Parallel fetch model_flags, model_rubrics, model_positions
    2. Group sub-resources by model_id
    3. Create entries using black-box entry creation tools
    """
    from app.infra.globals import get_redis_client
    from app.tools.entries.benchmark.create import create_benchmark
    from app.tools.entries.invocation.create import create_invocation
    from app.tools.resources.model_flags.get import get_model_flags
    from app.tools.resources.model_positions.get import (
        get_model_positions,
    )
    from app.tools.resources.model_rubrics.get import (
        get_model_rubrics,
    )

    if not model_ids:
        return 0

    # ── Pass 1: Parallel fetch all sub-resources ──
    async def _fetch_model_flags() -> list[Any]:
        async with pool.acquire() as c:
            return await get_model_flags(
                c, model_flag_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_model_rubrics() -> list[Any]:
        async with pool.acquire() as c:
            return await get_model_rubrics(
                c, model_rubric_ids, get_redis_client(), bypass_cache=True
            )

    async def _fetch_model_positions() -> list[Any]:
        async with pool.acquire() as c:
            return await get_model_positions(
                c, model_position_ids, get_redis_client(), bypass_cache=True
            )

    gather_results = await asyncio.gather(
        _fetch_model_flags(),
        _fetch_model_rubrics(),
        _fetch_model_positions(),
    )
    model_flags: list[Any] = cast(list[Any], gather_results[0])
    model_rubrics: list[Any] = cast(list[Any], gather_results[1])
    model_positions: list[Any] = cast(list[Any], gather_results[2])

    # ── Pass 2: Group sub-resources by model_id ──

    # model_id → list of flag resource IDs
    flags_by_model: dict[UUID, list[UUID]] = {}
    for mf in model_flags:
        if mf.model_id and mf.id:
            mid = UUID(str(mf.model_id))
            flags_by_model.setdefault(mid, []).append(mf.id)

    # model_id → list of rubric resource IDs
    rubrics_by_model: dict[UUID, list[UUID]] = {}
    for mr in model_rubrics:
        if mr.model_id and mr.id:
            mid = UUID(str(mr.model_id))
            rubrics_by_model.setdefault(mid, []).append(mr.id)

    # model_id → list of position resource IDs + position values
    positions_by_model: dict[UUID, list[tuple[UUID, int]]] = {}
    for mp in model_positions:
        if mp.model_id and mp.id:
            mid = UUID(str(mp.model_id))
            positions_by_model.setdefault(mid, []).append(
                (mp.id, mp.value if mp.value is not None else 0)
            )

    # ── Pass 3: Create entries using black-box tools ──

    # Create benchmark entry
    async with pool.acquire() as conn:
        benchmark = await create_benchmark(
            conn,
            evals_ids=[evals_resource_id],
            departments_ids=department_ids or [],
        )

    entry_count = 0

    # Create invocation entry per model
    for model_id in model_ids:
        # Get position value (last position for this model, or 0)
        position = 0
        position_resource_ids: list[UUID] = []
        for pos_id, pos_val in positions_by_model.get(model_id, []):
            position_resource_ids.append(pos_id)
            position = pos_val

        rubric_resource_ids = rubrics_by_model.get(model_id, [])
        flag_resource_ids = flags_by_model.get(model_id, [])

        async with pool.acquire() as conn:
            await create_invocation(
                conn,
                benchmark_id=benchmark.id,
                use_custom=False,
                position=position,
                model_ids=[model_id],
                model_flag_ids=flag_resource_ids,
                model_rubric_ids=rubric_resource_ids,
                model_position_ids=position_resource_ids,
            )

        entry_count += 1

    return entry_count
