"""Input: scenario.text_download

Socket equivalent of POST /scenarios/text/download.
Returns base64-encoded text file data since sockets can't stream files.
"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, get_upload_folder, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.scenario.text_download import text_download_scenario_impl
from app.infra.scenario.types import TextDownloadScenarioApiRequest

internal_sio = get_internal_sio()


@sio.on("scenario.text_download")  # type: ignore
async def scenario_text_download(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = TextDownloadScenarioApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("scenario.text_download.failed", {
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
        operation="text_download",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: text_download_scenario_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            text_id=payload.text_id,
        ),
        arguments={"text_id": str(payload.text_id)},
        upload_folder=get_upload_folder(),
    )
