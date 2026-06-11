"""Eval benchmark entry sync — pre-create benchmark + invocation entries on eval save.

Atomic + idempotent: the whole scaffold (benchmark + every invocation) is
written in ONE transaction (all-or-nothing), and a re-run for the same eval
first deactivates that eval's prior generated benchmark rows + their
invocations before re-creating, so ``/eval/update`` calling this on every save
REPLACES the scaffold instead of appending duplicates. The clear is scoped to
the single eval via ``benchmark_evals_connection``; other evals are untouched.
Uses black-box entry creation tools for the writes; the scoped deactivation is
a single guarded SQL statement.
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
    flag_ids: list[UUID] | None = None,
) -> int:
    """Sync benchmark entries by pre-creating benchmark + invocation entries.

    Three-pass approach:
    1. Parallel fetch model_flags, model_rubrics, model_positions, flags
    2. Group sub-resources by model_id; derive eval-level + per-model flag bools
    3. Create entries using black-box entry creation tools
    """
    from app.infra.globals import get_redis_client
    from app.tools.entries.benchmark.create import create_benchmark
    from app.tools.entries.invocation.create import create_invocation
    from app.tools.resources.flags.get import get_flags
    from app.tools.resources.model_flags.get import get_model_flags
    from app.tools.resources.model_positions.get import (
        get_model_positions,
    )
    from app.tools.resources.model_rubrics.get import (
        get_model_rubrics,
    )

    redis = get_redis_client()

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

    async def _fetch_artifact_flags() -> list[Any]:
        if not flag_ids:
            return []
        async with pool.acquire() as c:
            return await get_flags(
                c, list(flag_ids), get_redis_client(), bypass_cache=True
            )

    gather_results = await asyncio.gather(
        _fetch_model_flags(),
        _fetch_model_rubrics(),
        _fetch_model_positions(),
        _fetch_artifact_flags(),
    )
    model_flags: list[Any] = cast(list[Any], gather_results[0])
    model_rubrics: list[Any] = cast(list[Any], gather_results[1])
    model_positions: list[Any] = cast(list[Any], gather_results[2])
    artifact_flags: list[Any] = cast(list[Any], gather_results[3])

    # ── Pass 2a: Eval-level flag bools from artifact flag_ids ──

    is_dynamic = any(
        getattr(f, "name", None) == "eval_dynamic" and getattr(f, "value", False)
        for f in artifact_flags
    )
    use_groups = any(
        getattr(f, "name", None) == "eval_groups" and getattr(f, "value", False)
        for f in artifact_flags
    )

    # ── Pass 2b: Resolve flag rows referenced by model_flags so we know
    # each linked flag's name + value (model_flags rows only carry flag_id).
    mf_flag_ids = list({mf.flag_id for mf in model_flags if getattr(mf, "flag_id", None)})
    mf_flag_map: dict[UUID, tuple[str, bool]] = {}
    if mf_flag_ids:
        async with pool.acquire() as c:
            mf_flags = await get_flags(
                c, mf_flag_ids, get_redis_client(), bypass_cache=True
            )
        for f in mf_flags:
            if f.id and f.name is not None:
                mf_flag_map[f.id] = (f.name, bool(getattr(f, "value", False)))

    # model_id → {flag_name: bool_value}
    flag_bools_by_model: dict[UUID, dict[str, bool]] = {}
    for mf in model_flags:
        if mf.model_id and mf.flag_id and mf.flag_id in mf_flag_map:
            mid = UUID(str(mf.model_id))
            name, value = mf_flag_map[mf.flag_id]
            flag_bools_by_model.setdefault(mid, {})[name] = value

    # ── Pass 2c: Group sub-resources by model_id ──

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
    #
    # All writes for this eval's benchmark scaffold run in ONE transaction so
    # the whole thing is all-or-nothing: if invocation N fails we must not be
    # left with a benchmark + 1..N-1 invocations committed (a silently broken
    # half-scaffold). The nested ``create_*`` impls open their own
    # ``conn.transaction()`` which asyncpg composes as SAVEPOINTs under this
    # outer one, so they nest correctly.
    #
    # The sync is also IDEMPOTENT: ``/eval/update`` re-runs it on every save,
    # and ``create_benchmark`` is a plain INSERT, so without a clear step each
    # re-run appended a fresh full benchmark+invocation set → duplicates. We
    # deactivate THIS eval's prior generated benchmark rows (and their
    # invocations) first, scoped via ``benchmark_evals_connection`` so other
    # evals' benchmarks are untouched. Reads gate on ``active = true``
    # (benchmark_mv), so deactivation removes the stale scaffold from every
    # consumer; we then create the fresh set inside the same transaction. A
    # retry is therefore safe — it replaces, never appends.
    entry_count = 0
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Idempotency clear: soft-delete prior generated benchmarks for
            # THIS eval and the invocations hanging off them. Scoped to the
            # single eval via the evals connection; ``generated = true`` keeps
            # us off any hand-authored benchmark that happens to link this
            # eval. Deactivating the parent connection row + the benchmark row
            # + child invocations is enough to drop them from benchmark_mv.
            await conn.execute(
                """
                WITH prior AS (
                    SELECT be.id
                    FROM benchmark_entry be
                    JOIN benchmark_evals_connection bec
                      ON bec.benchmark_id = be.id AND bec.active = true
                    WHERE bec.evals_id = $1
                      AND be.active = true
                      AND be.generated = true
                ),
                deact_inv AS (
                    UPDATE invocation_entry ie
                    SET active = false
                    WHERE ie.benchmark_id IN (SELECT id FROM prior)
                      AND ie.active = true
                    RETURNING 1
                ),
                deact_conn AS (
                    UPDATE benchmark_evals_connection bec
                    SET active = false
                    WHERE bec.benchmark_id IN (SELECT id FROM prior)
                      AND bec.active = true
                    RETURNING 1
                )
                UPDATE benchmark_entry be
                SET active = false
                WHERE be.id IN (SELECT id FROM prior)
                """,
                evals_resource_id,
            )

            # Create the fresh benchmark entry.
            benchmark = await create_benchmark(
                conn, redis,
                evals_ids=[evals_resource_id],
                departments_ids=department_ids or [],
                use_groups=use_groups,
                dynamic=is_dynamic,
            )

            # Create one invocation entry per model.
            for model_id in model_ids:
                # Get position value (last position for this model, or 0)
                position = 0
                position_resource_ids: list[UUID] = []
                for pos_id, pos_val in positions_by_model.get(model_id, []):
                    position_resource_ids.append(pos_id)
                    position = pos_val

                rubric_resource_ids = rubrics_by_model.get(model_id, [])
                flag_resource_ids = flags_by_model.get(model_id, [])
                model_flag_bools = flag_bools_by_model.get(model_id, {})

                await create_invocation(
                    conn, redis,
                    benchmark_id=benchmark.id,
                    use_custom=model_flag_bools.get("use_custom", False),
                    position=position,
                    model_ids=[model_id],
                    model_flag_ids=flag_resource_ids,
                    model_rubric_ids=rubric_resource_ids,
                    model_position_ids=position_resource_ids,
                )

                entry_count += 1

    return entry_count
