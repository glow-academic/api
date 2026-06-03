"""Input: persona.get"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.persona.get import get_persona_impl
from app.infra.persona.types import GetPersonaApiRequest

internal_sio = get_internal_sio()


@sio.on("persona.get")  # type: ignore
async def persona_get(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GetPersonaApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("persona.get.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Build per-section filters from the nested SectionFilter objects, mirroring
    # the HTTP adapter in app/routes/persona/get.py. GetPersonaApiRequest no
    # longer carries flat persona_id/*_search/*_show_selected fields.
    filters = {
        s: getattr(payload, s)
        for s in [
            "names", "descriptions", "colors", "icons", "instructions",
            "departments", "examples", "parameter_fields", "voices",
        ]
        if getattr(payload, s) is not None
    }

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="persona",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        runner=lambda: get_persona_impl(
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
