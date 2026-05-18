"""List endpoint for test invocations — composable infra pattern.

Promoted from /test/benchmark/search to /test/invocations to match the
canonical resource it returns: a paginated list of test invocations (each
row is a test that has been run). The plural form mirrors /attempt/search
and other list endpoints; benchmark is the (rubric-driven) grouping concept,
not the resource itself. Internal types still reference the historical
``Benchmark*`` naming; only the route path was promoted.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.benchmark.context import resolve_benchmark_search_context
from app.infra.benchmark.get import _build_history
from app.infra.benchmark.types import (
    BenchmarkHistoryResponse,
    BenchmarkRequest,
)
from app.infra.globals import get_pool, get_redis_client
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/invocations", response_model=BenchmarkHistoryResponse)
async def list_invocations(
    request: BenchmarkRequest,
    http_request: Request,
    response: Response,
) -> BenchmarkHistoryResponse:
    """List test invocations with pagination and filters."""
    tags = ["artifacts", "test", "invocations"]
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

        response.headers["X-Cache-Tags"] = ",".join(tags)
        return _build_history(ctx, request)

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="artifacts_test_invocations",
            request=http_request,
        )
