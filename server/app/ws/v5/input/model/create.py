"""Input: model.create"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.model.create import create_model_impl
from app.infra.model.types import CreateModelApiRequest

internal_sio = get_internal_sio()


@sio.on("model.create")  # type: ignore
async def model_create(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = CreateModelApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("model.create.failed", {
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
        artifact="model",
        operation="create",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: create_model_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.models,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
