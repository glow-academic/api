"""Search endpoint for benchmark history — composable infra pattern."""

from collections import Counter, defaultdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.benchmark.context import resolve_benchmark_search_context
from app.infra.globals import get_pool, get_redis_client
from app.infra.test.permissions import compute_test_status
from app.infra.benchmark.types import (
    BenchmarkHistoryItem,
    BenchmarkHistoryResponse,
    BenchmarkRequest,
)
from app.infra.v5_types import FilterOption
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/search", response_model=BenchmarkHistoryResponse)
async def search_benchmark_history(
    request: BenchmarkRequest,
    http_request: Request,
    response: Response,
) -> BenchmarkHistoryResponse:
    """Search benchmark test history with pagination and filters."""
    tags = ["artifacts", "benchmark", "search"]
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
    pool = get_pool()

    try:
        department_uuids = (
            [UUID(d) for d in request.department_ids]
            if request.department_ids
            else None
        )
        eval_uuids = (
            [UUID(e) for e in request.history_eval_ids]
            if request.history_eval_ids
            else None
        )
        date_from: datetime | None = None
        date_to: datetime | None = None
        if request.start_date:
            date_from = datetime.fromisoformat(request.start_date)
        if request.end_date:
            date_to = datetime.fromisoformat(request.end_date)

        # ── Resolve search context ────────────────────────────────────
        ctx = await resolve_benchmark_search_context(
            pool,
            get_redis_client(),
            eval_ids=eval_uuids,
            department_ids=department_uuids,
            date_from=date_from,
            date_to=date_to,
            is_archived=request.history_archived,
            sort_order=request.history_sort_order,
            limit=request.history_page_size,
            offset=request.history_page * request.history_page_size,
            bypass_cache=bypass_cache,
        )

        # ── Build history ─────────────────────────────────────────────
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
                    created_at=(
                        t.test_created_at.isoformat() if t.test_created_at else None
                    ),
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

        response.headers["X-Cache-Tags"] = ",".join(tags)
        return BenchmarkHistoryResponse(
            data=items,
            total_count=len(items),
            page=request.history_page,
            page_size=request.history_page_size,
            eval_options=eval_options,
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_benchmark_search",
            request=http_request,
        )
