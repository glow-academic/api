"""Input: cohort.create"""

from typing import Any

from app.infra.cohort.create import create_cohort_impl
from app.infra.cohort.types import CreateCohortApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("cohort.create")  # type: ignore
async def cohort_create(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = CreateCohortApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("cohort.create.failed", {
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
        artifact="cohort",
        operation="create",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: create_cohort_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            items=payload.cohorts,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
