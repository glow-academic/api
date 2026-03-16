"""Input: benchmark.search"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.infra.benchmark.context import resolve_benchmark_search_context
from app.infra.benchmark.types import BenchmarkHistoryItem, BenchmarkHistoryResponse, BenchmarkRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.test.permissions import compute_test_status
from app.infra.v5_types import FilterOption

internal_sio = get_internal_sio()


@sio.on("benchmark.search")  # type: ignore
async def benchmark_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = BenchmarkRequest(**data)
    except Exception as e:
        await internal_sio.emit("benchmark.search.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="benchmark",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: _run_search(pool, redis, payload),
        arguments=payload.model_dump(mode="json"),
    )


async def _run_search(pool, redis, request: BenchmarkRequest) -> BenchmarkHistoryResponse:
    """Mirrors the HTTP benchmark search route logic."""
    from collections import Counter, defaultdict

    department_uuids = (
        [UUID(d) for d in request.department_ids] if request.department_ids else None
    )
    eval_uuids = (
        [UUID(e) for e in request.history_eval_ids] if request.history_eval_ids else None
    )
    date_from: datetime | None = (
        datetime.fromisoformat(request.start_date) if request.start_date else None
    )
    date_to: datetime | None = (
        datetime.fromisoformat(request.end_date) if request.end_date else None
    )

    ctx = await resolve_benchmark_search_context(
        pool,
        redis,
        eval_ids=eval_uuids,
        department_ids=department_uuids,
        date_from=date_from,
        date_to=date_to,
        is_archived=request.history_archived,
        sort_order=request.history_sort_order,
        limit=request.history_page_size,
        offset=request.history_page * request.history_page_size,
    )

    tests = ctx.entries.get("tests", [])
    test_invocations = ctx.entries.get("test_invocations", [])
    evals_list = ctx.resources["evals"].selected if "evals" in ctx.resources else []

    eval_map = {ev.id: ev for ev in evals_list if ev.id}

    ti_by_test: dict[UUID, list] = defaultdict(list)
    for ti in test_invocations:
        if ti.test_id:
            ti_by_test[ti.test_id].append(ti)

    items: list[BenchmarkHistoryItem] = []
    eval_counter: Counter[str] = Counter()
    eval_id_to_name: dict[str, str | None] = {}

    for t in tests:
        tis = ti_by_test.get(t.test_id, [])
        total_inv = len(tis)
        completed_inv = sum(1 for ti in tis if ti.invocation_completed)

        best_score: float | None = None
        has_passed = False
        for ti in tis:
            if ti.grade_passed:
                has_passed = True
            if ti.grade_score is not None:
                if best_score is None or ti.grade_score > best_score:
                    best_score = ti.grade_score

        eval_name: str | None = None
        eval_desc: str | None = None
        if t.eval_id and t.eval_id in eval_map:
            eval_name = eval_map[t.eval_id].name
            eval_desc = eval_map[t.eval_id].description

        if t.eval_id:
            eid_str = str(t.eval_id)
            eval_counter[eid_str] += 1
            if eid_str not in eval_id_to_name:
                eval_id_to_name[eid_str] = eval_name

        items.append(
            BenchmarkHistoryItem(
                test_id=str(t.test_id),
                eval_id=str(t.eval_id) if t.eval_id else None,
                eval_name=eval_name,
                eval_description=eval_desc,
                created_at=t.test_created_at.isoformat() if t.test_created_at else None,
                archived=t.archived,
                infinite_mode=t.infinite_mode,
                total_invocations=total_inv,
                completed_invocations=completed_inv,
                pending_invocations=total_inv - completed_inv,
                best_score=best_score,
                has_passed=has_passed,
                status=compute_test_status(total_inv, completed_inv),
            )
        )

    eval_options = [
        FilterOption(value=eid, label=eval_id_to_name.get(eid), count=count)
        for eid, count in eval_counter.items()
    ]
    eval_options.sort(key=lambda o: o.value)

    return BenchmarkHistoryResponse(
        data=items,
        total_count=len(items),
        page=request.history_page,
        page_size=request.history_page_size,
        eval_options=eval_options,
    )
