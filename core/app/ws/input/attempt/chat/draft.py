"""Input: chat.draft"""

from typing import Any

from app.infra.chat.draft import patch_chat_draft_impl
from app.infra.chat.types import PatchChatDraftApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


@sio.on("attempt.draft")  # type: ignore
async def attempt_draft_ack(sid: str, data: dict[str, Any]) -> dict[str, Any]:
    """Ack-based handler — returns draft_id directly via socket.io acknowledgement."""
    identity = await resolve_socket_identity(sid)
    if not identity:
        return {"error": "Not authenticated"}

    try:
        payload = PatchChatDraftApiRequest(**data)
        pool = get_pool()
        redis = get_redis_client()
        result = await patch_chat_draft_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            request=payload,
        )
        return result.model_dump(mode="json") if hasattr(result, "model_dump") else {"draft_id": str(result)}
    except Exception as e:
        return {"error": str(e)}
