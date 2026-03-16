"""Input: home.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.home.types import GetHomeRequest
from app.infra.identity.socket import resolve_socket_identity
from app.routes.v5.home.get import get_home_internal

internal_sio = get_internal_sio()


@sio.on("home.get")  # type: ignore
async def home_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetHomeRequest(**data)
    except Exception as e:
        await internal_sio.emit("home.get.failed", {
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
        artifact="home",
        operation="get",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_home_internal(
            pool,
            identity.profile_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
