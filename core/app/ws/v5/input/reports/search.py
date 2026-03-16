"""Input: reports.search"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.reports.get import get_reports_impl
from app.infra.reports.types import ReportsRequest

internal_sio = get_internal_sio()


@sio.on("reports.search")  # type: ignore
async def reports_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ReportsRequest(**data)
    except Exception as e:
        await internal_sio.emit("reports.search.failed", {
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
        artifact="reports",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_reports_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
