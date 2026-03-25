"""Input: persona.get"""

from typing import Any
from uuid import UUID

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

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="persona",
        operation="get",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        draft_id=payload.draft_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_persona_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            persona_id=payload.persona_id,
            draft_id=payload.draft_id,
            parameter_ids=[UUID(pid) for pid in payload.parameter_ids]
            if payload.parameter_ids
            else None,
            color_search=payload.color_search,
            icon_search=payload.icon_search,
            descriptions_search=payload.descriptions_search,
            instructions_search=payload.instructions_search,
            color_show_selected=payload.color_show_selected,
            icon_show_selected=payload.icon_show_selected,
        ),
        arguments=payload.model_dump(mode="json"),
    )
