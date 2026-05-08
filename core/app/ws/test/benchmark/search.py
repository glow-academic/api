"""Input: benchmark.search"""

from datetime import datetime
from typing import Any
from uuid import UUID

from app.infra.benchmark.context import resolve_benchmark_search_context
from app.infra.benchmark.get import _build_history
from app.infra.benchmark.types import BenchmarkHistoryResponse, BenchmarkRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("test.benchmark.search")  # type: ignore
async def benchmark_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = BenchmarkRequest(**data)
    except Exception as e:
        await internal_sio.emit("test.benchmark_search.failed", {
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
        artifact="test",
        operation="benchmark_search",
        profile_id=identity.profile_id,
        sid=sid,
        runner=lambda: _run_search(pool, redis, payload),
        arguments=payload.model_dump(mode="json"),
    )


async def _run_search(pool, redis, request: BenchmarkRequest) -> BenchmarkHistoryResponse:
    """Mirrors the HTTP benchmark search route logic."""
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

    return _build_history(ctx, request)
