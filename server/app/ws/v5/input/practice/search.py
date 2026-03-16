"""Input: practice.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.routes.v5.practice.get import get_practice_internal

internal_sio = get_internal_sio()


class PracticeSearchPayload(BaseModel):
    """Payload for practice.search socket event."""

    sort_by: str | None = Field("date")
    sort_order: str | None = Field("desc")
    page: int = Field(0)
    page_size: int = Field(20)
    simulation_search: str | None = Field(None)
    scenario_search: str | None = Field(None)
    show_archived: bool = Field(False)
    scenario_ids: list[UUID] | None = Field(None)
    infinite_mode: bool | None = Field(None)


@sio.on("practice.search")  # type: ignore
async def practice_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = PracticeSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("practice.search.failed", {
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
        artifact="practice",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_practice_internal(
            pool,
            profile_id=identity.profile_id,
        ),
        arguments=payload.model_dump(mode="json"),
    )
