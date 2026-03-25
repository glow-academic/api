"""Input: cohort.docs"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.cohort.docs import docs_cohort_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class CohortDocsPayload(BaseModel):
    """Payload for cohort.docs socket event."""

    entity_id: UUID | None = Field(None)


@sio.on("cohort.docs")  # type: ignore
async def cohort_docs(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = CohortDocsPayload(**data)
    except Exception as e:
        await internal_sio.emit("cohort.docs.failed", {
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
        artifact="cohort",
        operation="docs",
        profile_id=identity.profile_id,
        entity_id=payload.entity_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: docs_cohort_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            entity_id=payload.entity_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
