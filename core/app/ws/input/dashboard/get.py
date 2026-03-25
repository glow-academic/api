"""Input: dashboard.get"""

from typing import Any

from app.infra.dashboard.get import get_dashboard_impl_cached
from app.infra.dashboard.types import DashboardRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("dashboard.get")  # type: ignore
async def dashboard_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DashboardRequest(**data)
    except Exception as e:
        await internal_sio.emit("dashboard.get.failed", {
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
        artifact="dashboard",
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_dashboard_impl_cached(
            pool,
            payload,
            profile_id=identity.profile_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
