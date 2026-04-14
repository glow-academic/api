"""Input: simulation.group"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.simulation.group import (
    GroupSimulationApiRequest,
    group_simulation_impl,
)


@sio.on("simulation.group")  # type: ignore
async def simulation_group(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GroupSimulationApiRequest(**data)
    except Exception:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="simulation",
        operation="group",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: group_simulation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
