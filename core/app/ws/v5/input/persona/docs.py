"""Input: persona.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.persona.docs import docs_persona_impl

internal_sio = get_internal_sio()


class PersonaDocsPayload(BaseModel):
    """Payload for persona.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("persona.docs")  # type: ignore
async def persona_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = PersonaDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("persona.docs.failed", {
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
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_persona_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
