"""Profiles SEARCH — reusable data-access layer."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.infra.search.search_resource import search_resource_ids
from app.tools.resources.profiles.get import get_profiles
from app.tools.resources.profiles.types import GetProfileResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

JUNCTION_ARTIFACTS = [
    "cohort",
    "profile",
    "setting",
]

DRAFT_ARTIFACTS = [
    "agent",
    "auth",
    "chat",
    "cohort",
    "department",
    "document",
    "eval",
    "field",
    "invocation",
    "model",
    "parameter",
    "persona",
    "provider",
    "rubric",
    "scenario",
    "setting",
    "simulation",
    "tool",
]


async def search_profiles(
    conn: asyncpg.Connection,
    redis: Redis,
    search: str | None = None,
    limit_count: int = 20,
    offset_count: int = 0,
    draft_id: UUID | None = None,
    suggest_source: str | None = None,
    exclude_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    bypass_cache: bool = False,
    *,
    cohort: bool = False,
    profile: bool = False,
    setting: bool = False,
) -> list[GetProfileResponse]:
    """Search profiles with optional artifact/draft filters."""
    if limit_count <= 0:
        return []

    artifact_filters = {
        "cohort": cohort,
        "profile": profile,
        "setting": setting,
    }

    tags = ["resources", "profiles"]
    key = cache_key(
        "/v5/resources/profiles/search",
        {
            "search": search,
            "limit_count": limit_count,
            "offset_count": offset_count,
            "draft_id": str(draft_id) if draft_id else None,
            "suggest_source": suggest_source,
            "exclude_ids": [str(i) for i in (exclude_ids or [])],
            "department_ids": sorted(str(i) for i in (department_ids or [])),
            "cohort_ids": sorted(str(i) for i in (cohort_ids or [])),
            "role_ids": sorted(str(i) for i in (role_ids or [])),
            **artifact_filters,
        },
    )

    if not bypass_cache:
        cached = await get_cached(key, redis=redis)
        if cached:
            return [
                GetProfileResponse.model_validate(item)
                for item in cached.get("items", [])
            ]

    # Build extra conditions for profile-specific filters
    extra_conditions: list[tuple[str, object]] = []
    extra_conditions.append(("{alias}.active = ${idx}", True))
    if department_ids:
        extra_conditions.append(
            ("{alias}.department_ids && ${idx}", department_ids),
        )
    if cohort_ids:
        extra_conditions.append(
            (
                "EXISTS (SELECT 1 FROM cohorts_resource cr WHERE {alias}.id = ANY(cr.profile_ids) AND cr.id = ANY(${idx}))",
                cohort_ids,
            ),
        )
    if role_ids:
        extra_conditions.append(
            ("{alias}.role_id = ANY(${idx})", role_ids),
        )

    ids = await search_resource_ids(
        conn,
        table="profiles_resource",
        resource="profiles",
        search_column="name",
        search=search,
        limit_count=limit_count,
        offset_count=offset_count,
        exclude_ids=exclude_ids,
        draft_id=draft_id,
        suggest_source=suggest_source,
        artifact_filters=artifact_filters,
        junction_artifacts=JUNCTION_ARTIFACTS,
        draft_artifacts=DRAFT_ARTIFACTS,
        extra_conditions=extra_conditions if extra_conditions else None,
    )

    if not ids:
        await set_cached(key, {"items": []}, 60, tags, redis=redis)
        return []

    items = await get_profiles(conn, ids, redis, bypass_cache=True)

    await set_cached(
        key,
        {"items": [i.model_dump(mode="json") for i in items]},
        60,
        tags,
        redis=redis,
    )
    return items
