"""Input: scenario.export"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.export import export_scenario_impl
from app.infra.scenario.types import ExportScenarioApiRequest

internal_sio = get_internal_sio()


@sio.on("scenario.export")  # type: ignore
async def scenario_export(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = ExportScenarioApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("scenario.export.failed", {
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
        artifact="scenario",
        operation="export",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: export_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            scenario_id=payload.scenario_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
