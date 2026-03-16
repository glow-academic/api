"""Input: eval.update"""

from typing import Any

from app.infra.eval.types import UpdateEvalApiRequest
from app.infra.eval.update import update_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("eval.update")  # type: ignore
async def eval_update(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = UpdateEvalApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("eval.update.failed", {
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
        artifact="eval",
        operation="update",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: update_eval_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.evals,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
