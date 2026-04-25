"""Auth search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_auths (artifact) — core artifact search (IDs + total_count)
  3. get_auths (artifact) — hydrate junction IDs
  4. Resource get tools — hydrate names, descriptions
  5. Permissions — compute per-auth can_edit, can_delete, can_duplicate
  6. Facets — department search for filter options
  7. active_settings_count — for edit/delete permission checks
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.auth.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.auth.permissions_context import (
    AuthPermissionsContext,
    resolve_auth_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.auth.types import (
    ListAuthApiAuth,
    ListAuthApiResponse,
)
from app.infra.api_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.auth.get import get_auths
from app.tools.artifacts.auth.search import (
    search_auths as search_auth_artifacts,
)
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)


async def search_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 1000,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListAuthApiResponse:
    """auth search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("auth/search", {
            "profile_id": str(profile_id),
            "search": search,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "department_search": department_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "auth", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListAuthApiResponse,
        builder=lambda: _search_auth_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            filter_department_ids=filter_department_ids,
            department_search=department_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_auth_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    department_search: str | None = None,
    flag_search: str | None = None,
    # Pagination
    page_size: int = 1000,
    page_offset: int = 0,
) -> ListAuthApiResponse:
    """Auth search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, departments, name
      2. search_auths → (auth_artifact_ids, total_count)
      3. get_auths → hydrate junction IDs
      4. Parallel: hydrate resources + facets + active_settings_counts
      5. Compute permissions per auth
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role_level = profile.role_level
    actor_name = profile.name

    # ── Step 2: Search auths ──────────────────────────────────────────

    async with pool.acquire() as conn:
        auth_ids, total_count = await search_auth_artifacts(
            conn,
            search=search,
            department_ids=filter_department_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not auth_ids:
        # Still fetch facets for empty results
        async with pool.acquire() as conn:
            department_facet = await search_departments(
                conn, redis, search=department_search, auth=True, limit_count=100
            )
            flag_facet = await search_flags(
                conn, redis, search=flag_search, auth=True, limit_count=100
            )

        department_filter = ListFilterSection(
            options=[
                ListFilterOption(id=str(d.id), name=d.name, count=0)
                for d in department_facet
            ],
            selected_ids=[str(did) for did in filter_department_ids]
            if filter_department_ids
            else None,
            search=department_search,
        )

        flag_filter = ListFilterSection(
            options=[
                ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
                for f in flag_facet
            ],
            search=flag_search,
        )

        return ListAuthApiResponse(
            actor_name=actor_name,
            auths=[],
            department_filter=department_filter,
            flag_filter=flag_filter,
            total_count=0,
        )

    # ── Step 3: Get auth artifacts with junction IDs ──────────────────

    async with pool.acquire() as conn:
        artifacts = await get_auths(
            conn,
            auth_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            items=True,
            auths=True,
        )

    # Build per-auth setting_ids map (setting_artifact ids that reference any
    # of this auth's auths_resource rows via setting_auths_junction).
    settings_by_auth_resource: dict[UUID, list[UUID]] = {}
    all_auth_resource_ids: list[UUID] = []
    for a in artifacts:
        all_auth_resource_ids.extend(a.auth_ids or [])
    if all_auth_resource_ids:
        async with pool.acquire() as conn:
            setting_rows = await conn.fetch(
                """
                SELECT auths_id,
                       ARRAY_AGG(DISTINCT setting_id)
                         FILTER (WHERE setting_id IS NOT NULL) AS setting_ids
                FROM setting_auths_junction
                WHERE auths_id = ANY($1) AND active = true
                GROUP BY auths_id
                """,
                all_auth_resource_ids,
            )
        for r in setting_rows:
            settings_by_auth_resource[r["auths_id"]] = list(r["setting_ids"] or [])

    # Build per-auth auth_item_key_ids map (auth_item_keys_resource rows owned
    # by this auth_artifact via auth_item_keys_resource.auth_id).
    auth_item_keys_by_auth: dict[UUID, list[UUID]] = {}
    if auth_ids:
        async with pool.acquire() as conn:
            key_rows = await conn.fetch(
                """
                SELECT auth_id,
                       ARRAY_AGG(DISTINCT id)
                         FILTER (WHERE id IS NOT NULL) AS key_ids
                FROM auth_item_keys_resource
                WHERE auth_id = ANY($1) AND active = true
                GROUP BY auth_id
                """,
                auth_ids,
            )
        for r in key_rows:
            auth_item_keys_by_auth[r["auth_id"]] = list(r["key_ids"] or [])

    # ── Step 4: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    # Per-auth permissions context (gives us active_settings_count)
    async def _fetch_names_data() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions_data() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as c:
            return await get_descriptions(c, all_description_ids, redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as c:
            return await search_departments(
                c, redis, search=department_search, auth=True, limit_count=100
            )

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as c:
            return await search_flags(
                c, redis, search=flag_search, auth=True, limit_count=100
            )

    async def _fetch_perms(artifact_id: UUID) -> AuthPermissionsContext:
        async with pool.acquire() as c:
            return await resolve_auth_permissions_context(c, artifact_id)

    perm_tasks = [_fetch_perms(a.id) for a in artifacts]

    (
        names_data,
        descriptions_data,
        department_facet,
        flag_facet,
        *perm_results,
    ) = await asyncio.gather(
        _fetch_names_data(),
        _fetch_descriptions_data(),
        _fetch_department_facet(),
        _fetch_flag_facet(),
        *perm_tasks,
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    # ── Step 5: Build auth list with permissions ──────────────────────

    auths_list: list[ListAuthApiAuth] = []

    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_settings_count = perm_results[i].active_settings_count
        item_count = len(a.item_ids or [])

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            active_settings_count=active_settings_count,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            active_settings_count=active_settings_count,
        )
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        # Aggregate setting_ids across this auth's auths_resource rows.
        auth_setting_ids: list[UUID] = []
        seen_setting_ids: set[UUID] = set()
        for ar_id in a.auth_ids or []:
            for sid in settings_by_auth_resource.get(ar_id, []):
                if sid not in seen_setting_ids:
                    seen_setting_ids.add(sid)
                    auth_setting_ids.append(sid)

        auths_list.append(
            ListAuthApiAuth(
                auth_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                item_count=item_count,
                department_ids=dept_ids_str,
                setting_ids=auth_setting_ids,
                auth_item_key_ids=list(auth_item_keys_by_auth.get(a.id, [])),
                is_inactive=not a.active,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
            )
        )

    # ── Step 6: Build facet sections ──────────────────────────────────

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in filter_department_ids]
        if filter_department_ids
        else None,
        search=department_search,
    )

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListAuthApiResponse(
        actor_name=actor_name,
        auths=auths_list,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


async def _empty_list() -> list:
    return []
