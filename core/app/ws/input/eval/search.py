"""Input: eval.search"""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.infra.eval.search import search_eval_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity

internal_sio = get_internal_sio()


class EvalSearchPayload(BaseModel):
    """Payload for eval.search socket event."""

    search: str | None = Field(None)
    filter_department_ids: list[UUID] | None = Field(None)
    department_search: str | None = Field(None)
    page_size: int = Field(50)
    page_offset: int = Field(0)


@sio.on("eval.search")  # type: ignore
async def eval_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = EvalSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("eval.search.failed", {
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
        artifact="eval",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: search_eval_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            search=payload.search,
            filter_department_ids=payload.filter_department_ids,
            department_search=payload.department_search,
            page_size=payload.page_size,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
