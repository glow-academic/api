"""Input: pricing.search"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.socket import resolve_socket_identity
from app.infra.pricing.get import get_pricing_impl
from app.infra.pricing.types import PricingRequest

internal_sio = get_internal_sio()


class PricingSearchPayload(BaseModel):
    """Payload for pricing.search socket event."""

    start_date: datetime | None = Field(default=None)
    end_date: datetime | None = Field(default=None)
    date_from: datetime | None = Field(default=None)
    date_to: datetime | None = Field(default=None)
    page: int = Field(0)
    page_size: int = Field(50)
    sort_order: str = Field("desc")


@sio.on("pricing.search")  # type: ignore
async def pricing_search(sid: str, data: dict[str, Any]) -> None:
    identity = await resolve_socket_identity(sid)
    if not identity:
        return

    try:
        payload = PricingSearchPayload(**data)
    except Exception as e:
        await internal_sio.emit("pricing.search.failed", {
            "sid": sid,
            "rooms": [sid],
            "message": str(e),
            "error_type": "validation",
        })
        return

    pool = get_pool()
    redis = get_redis_client()

    # Pricing search reuses the get impl with the request params
    request = PricingRequest(
        start_date=payload.start_date,
        end_date=payload.end_date,
        date_from=payload.date_from,
        date_to=payload.date_to,
    )

    await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="pricing",
        operation="search",
        profile_id=identity.profile_id,
        sid=sid,
        rooms=[sid],
        runner=lambda: get_pricing_impl(
            pool,
            redis,
            profile_id=identity.profile_id,
            request=request,
        ),
        arguments=payload.model_dump(mode="json"),
    )
