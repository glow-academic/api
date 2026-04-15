"""Input: pricing.generations"""

from typing import Any

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.pricing.generations import generations_pricing_impl
from app.infra.pricing.types import GenerationsPricingApiRequest

internal_sio = get_internal_sio()


@sio.on("system.pricing.generations")  # type: ignore
async def pricing_generations(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = GenerationsPricingApiRequest(**data)
    except Exception as e:
        await internal_sio.emit("pricing.generations.failed", {
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
        artifact="pricing",
        operation="generations",
        profile_id=identity.profile_id,
        session_id=identity.session_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: generations_pricing_impl(
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
