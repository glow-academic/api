"""Input: simulation.delete"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.simulation.delete import delete_simulation_impl
from app.infra.simulation.types import DeleteSimulationApiRequest

internal_sio = get_internal_sio()


@sio.on("simulation.delete")  # type: ignore
async def simulation_delete(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = DeleteSimulationApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("simulation.delete.failed", {
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
        artifact="simulation",
        operation="delete",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: delete_simulation_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            simulation_ids=payload.simulation_ids,
            session_id=identity.session_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
