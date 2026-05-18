"""Input: scenario.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.get import SECTIONS, get_scenario_impl
from app.infra.scenario.types import GetScenarioApiRequest

internal_sio = get_internal_sio()


@sio.on("scenario.get")  # type: ignore
async def scenario_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetScenarioApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("scenario.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Build filters dict from nested SectionFilter objects
    filters = {
        s: getattr(payload, s)
        for s in SECTIONS
        if getattr(payload, s) is not None
    }

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="scenario",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        runner=lambda: get_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            id=payload.id,
            draft_id=payload.draft_id,
            filters=filters,
        ),
        arguments=payload.model_dump(mode="json"),
    )
