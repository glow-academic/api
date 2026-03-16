"""Input: cohort.get"""

from typing import Any

from app.infra.cohort.get import get_cohort_impl
from app.infra.cohort.types import GetCohortApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("cohort.get")  # type: ignore
async def cohort_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetCohortApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("cohort.get.failed", {
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
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_cohort_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            cohort_id=payload.cohort_id,
            draft_id=payload.draft_id,
            descriptions_search=payload.descriptions_search,
            simulation_search=payload.simulation_search,
            simulation_show_selected=payload.simulation_show_selected,
            profile_search=payload.profile_search,
            profile_show_selected=payload.profile_show_selected,
        ),
        arguments=payload.model_dump(mode="json"),
    )
