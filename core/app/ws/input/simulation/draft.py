"""Input: simulation.draft"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.simulation.draft import patch_simulation_draft_impl
from app.infra.simulation.types import PatchSimulationDraftApiRequest

internal_sio = get_internal_sio()


@sio.on("simulation.draft")  # type: ignore
async def simulation_draft(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = PatchSimulationDraftApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("simulation.draft.failed", {
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
        operation="draft",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: patch_simulation_draft_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        ),
        arguments=payload.model_dump(mode="json"),
    )
