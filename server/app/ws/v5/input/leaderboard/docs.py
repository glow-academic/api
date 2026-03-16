"""Input: leaderboard.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.leaderboard.docs import docs_leaderboard_impl

internal_sio = get_internal_sio()


class LeaderboardDocsPayload(BaseModel):
    """Payload for leaderboard.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("leaderboard.docs")  # type: ignore
async def leaderboard_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = LeaderboardDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("leaderboard.docs.failed", {
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
        artifact="leaderboard",
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_leaderboard_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
