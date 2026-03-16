"""Profiles Resource GET — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.profiles.types import GetProfileResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_profiles(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    bypass_cache: bool = False,
) -> list[GetProfileResponse]:
    """Fetch profiles_resource entries by IDs."""
    if not ids:
        return []

    tags = ["resources", "profiles"]
    key = cache_key("/v5/resources/profiles/get", {"ids": [str(id) for id in ids]})

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProfileResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    rows = await conn.fetch(
        """
        SELECT id, name, description, role, department_ids,
               role_id, emails, primary_email, requests_per_day,
               last_login, created_at, active, mcp, generated
        FROM profiles_resource
        WHERE id = ANY($1)
        ORDER BY array_position($1, id)
    """,
        ids,
    )

    items = [
        GetProfileResponse(
            id=r["id"],
            name=r["name"],
            description=r["description"],
            role=r["role"],
            department_ids=r["department_ids"] or [],
            role_id=r["role_id"],
            emails=r["emails"] or [],
            primary_email=r["primary_email"],
            requests_per_day=r["requests_per_day"],
            last_login=r["last_login"],
            created_at=r["created_at"],
            active=r["active"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]

    if not bypass_cache:
        await set_cached(
            key,
            {"items": [i.model_dump(mode="json") for i in items]},
            60,
            tags,
            redis=redis,
        )
    return items
