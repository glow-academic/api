"""Logins SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.logins.get import get_logins
from app.tools.resources.logins.types import GetLoginsResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def search_logins(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    exclude_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    login_type: str | None = None,
    bypass_cache: bool = False,
) -> list[GetLoginsResponse]:
    """Search logins_resource with optional filters."""
    if limit_count <= 0:
        return []

    tags = ["resources", "logins"]
    key = cache_key(
        "/resources/logins/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "profile_ids": sorted(str(i) for i in (profile_ids or [])),
            "auth_ids": sorted(str(i) for i in (auth_ids or [])),
            "login_type": login_type,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetLoginsResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    conditions = ["active = true"]
    params: list[object] = []
    idx = 1

    if search:
        conditions.append(f"display_name ILIKE ${idx}")
        params.append(f"%{search}%")
        idx += 1

    if exclude_ids:
        conditions.append(f"id != ALL(${idx}::uuid[])")
        params.append(exclude_ids)
        idx += 1

    if profile_ids:
        conditions.append(f"profile_id = ANY(${idx}::uuid[])")
        params.append(profile_ids)
        idx += 1

    if auth_ids:
        conditions.append(f"auth_id = ANY(${idx}::uuid[])")
        params.append(auth_ids)
        idx += 1

    if login_type:
        conditions.append(f"login_type = ${idx}")
        params.append(login_type)
        idx += 1

    where = " AND ".join(conditions)
    query = f"""
        SELECT id
        FROM logins_resource
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT {limit_count} OFFSET {offset_count}
    """

    rows = await conn.fetch(query, *params)
    ids = [r["id"] for r in rows]

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_logins(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
