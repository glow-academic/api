"""Input: persona.drafts"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.persona.drafts import list_persona_drafts_impl


@sio.on("persona.drafts")  # type: ignore
async def persona_drafts(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    pool = get_pool()
    redis = get_redis_client()

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="persona",
        operation="drafts",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: list_persona_drafts_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
        ),
        arguments={},
    )
