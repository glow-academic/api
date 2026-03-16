"""Auth Item Keys SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.auth_item_keys.get import get_auth_item_keys
from app.tools.resources.auth_item_keys.types import GetAuthItemKeyResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = ["setting"]


async def search_auth_item_keys(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    key_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    setting: bool = False,
) -> list[GetAuthItemKeyResponse]:
    """Search auth_item_keys with optional artifact filters.

    Note: text search is across joined tables (auths_resource, keys_resource),
    so this uses a direct query rather than search_resource_ids.
    """
    if limit_count <= 0:
        return []

    artifact_filters = {
        "setting": setting,
    }

    tags = ["resources", "auth_item_keys"]
    key = cache_key(
        "/v5/resources/auth_item_keys/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "auth_ids": sorted(str(i) for i in (auth_ids or [])),
            "key_ids": sorted(str(i) for i in (key_ids or [])),
            "item_ids": sorted(str(i) for i in (item_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetAuthItemKeyResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build dynamic WHERE for ID search
    # auth_item_keys searches across joined tables for text, so we use a direct query
    alias = "akr"
    conditions: list[str] = [f"{alias}.active = true"]
    params: list[object] = []
    idx = 1

    # Text search across joined table columns
    if search:
        conditions.append(
            f"(LOWER(COALESCE(ar.name, '')) LIKE '%' || LOWER(${idx}) || '%'"
            f" OR LOWER(COALESCE(kr.name, '')) LIKE '%' || LOWER(${idx}) || '%'"
            f" OR LOWER(COALESCE(kr.description, '')) LIKE '%' || LOWER(${idx}) || '%')"
        )
        params.append(search)
        idx += 1

    # Exclude filter
    if exclude_ids:
        conditions.append(f"NOT ({alias}.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # FK-based filters
    if auth_ids:
        conditions.append(f"{alias}.auth_id = ANY(${idx})")
        params.append(auth_ids)
        idx += 1
    if key_ids:
        conditions.append(f"{alias}.key_id = ANY(${idx})")
        params.append(key_ids)
        idx += 1
    if item_ids:
        conditions.append(f"{alias}.item_id = ANY(${idx})")
        params.append(item_ids)
        idx += 1

    # Artifact junction filters
    if artifact_filters.get("setting"):
        conditions.append(
            f"EXISTS (SELECT 1 FROM setting_auth_item_keys_junction j WHERE j.auth_item_keys_id = {alias}.id AND j.active = true)"
        )

    where = " AND ".join(conditions)
    query = f"""
        SELECT {alias}.id
        FROM auth_item_keys_resource {alias}
        LEFT JOIN auths_resource ar ON ar.id = {alias}.auth_id
        LEFT JOIN keys_resource kr ON kr.id = {alias}.key_id
        WHERE {where}
        ORDER BY COALESCE(ar.name, ''), COALESCE(kr.name, '')
        LIMIT ${idx} OFFSET ${idx + 1}
    """
    params.extend([limit_count, offset_count])

    rows = await conn.fetch(query, *params)
    ids = [row["id"] for row in rows]

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_auth_item_keys(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
