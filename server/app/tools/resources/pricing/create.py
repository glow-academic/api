"""Pricing CREATE — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.pricing.get import get_pricing
from app.tools.resources.pricing.types import GetPricingResponse
from app.utils.cache.invalidate_tags import invalidate_tags


async def create_pricing(
    conn: asyncpg.Connection,
    pricing_type: str,
    price: float,
    unit_name: str,
    unit_category: str,
    unit_value: int,
    redis: Redis,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
) -> GetPricingResponse:
    """Create a pricing resource (plain INSERT, no unique constraint)."""
    pricing_id = await conn.fetchval(
        """
        INSERT INTO pricing_resource
            (id, pricing_type, price, unit_name, unit_category, unit_value, active, mcp, generated)
        VALUES (COALESCE($8, uuidv7()), $1::pricing_type, $2, $3, $4::unit_type, $5, $6, $7, $7)
        RETURNING id
        """,
        pricing_type,
        price,
        unit_name,
        unit_category,
        unit_value,
        not soft,
        mcp,
        id,
    )
    await invalidate_tags(["resources", "pricing"], redis=redis)
    items = await get_pricing(conn, [pricing_id], redis, bypass_cache=True)
    return items[0]
