"""Input: practice.generations"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.practice.generations import generations_practice_impl
from app.infra.practice.types import GenerationsPracticeApiRequest

internal_sio = get_internal_sio()


@sio.on("attempt.practice.generations")  # type: ignore
async def practice_generations(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GenerationsPracticeApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("practice.generations.failed", {
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
        operation="generations",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: generations_practice_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            session_id=identity.session_id,
            search=payload.search,
            date_from=payload.date_from,
            date_to=payload.date_to,
            page_limit=payload.page_limit,
            page_offset=payload.page_offset,
        ),
        arguments=payload.model_dump(mode="json"),
    )
