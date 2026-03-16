"""Input: benchmark.get"""

from typing import Any

from app.infra.benchmark.get import get_benchmark_impl
from app.infra.benchmark.types import BenchmarkRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("benchmark.get")  # type: ignore
async def benchmark_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = BenchmarkRequest(**data)
    except Exception as e:
        await internal_sio.emit("benchmark.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_benchmark_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
