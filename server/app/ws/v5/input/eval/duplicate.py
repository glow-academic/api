"""Input: eval.duplicate"""

from typing import Any

from app.infra.eval.duplicate import duplicate_eval_impl
from app.infra.eval.types import DuplicateEvalApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("eval.duplicate")  # type: ignore
async def eval_duplicate(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DuplicateEvalApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("eval.duplicate.failed", {
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
        operation="duplicate",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: duplicate_eval_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            eval_id=payload.eval_id,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
