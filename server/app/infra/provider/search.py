"""Provider search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. Reverse lookups — model_ids → provider_ids via models_resource
  3. search_providers — core artifact search (IDs + total_count)
  4. get_providers — hydrate junction IDs
  5. Resource get tools — hydrate names, descriptions
  6. Permissions — compute per-provider can_edit, can_delete, can_duplicate
  7. Facets — parallel resource searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.provider.types import (
    ListProviderApiProvider,
    ListProviderApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.provider.get import get_providers
from app.tools.artifacts.provider.search import search_providers
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.models.search import (
    search_models as search_models_resource,
)
from app.tools.resources.names.get import get_names
from app.tools.resources.providers.get import (
    get_providers as get_providers_resource,
)
from app.tools.resources.values.get import get_values

PROVIDER_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "OpenAI",
        "description": "The provider's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "OpenAI API provider...",
        "description": "Optional description",
    },
    {
        "key": "active_flag",
        "label": "Active",
        "type": "boolean",
        "example": "true",
        "description": "Whether the provider is active (true/false)",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
]


async def search_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    filter_department_ids: list[UUID] | None = None,
    filter_model_ids: list[UUID] | None = None,
    filter_status: list[str] | None = None,
    # Facet search text
    department_search: str | None = None,
    model_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListProviderApiResponse:
    """Provider search using composable infra functions."""
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # ── Step 2: Reverse lookups ────────────────────────────────────────

    provider_resource_ids: list[UUID] | None = None

    if filter_model_ids:
        # model_ids filter references model_artifact IDs
        # Models have providers_junction → get provider resource IDs
        from app.tools.artifacts.model.get import (
            get_models as get_model_artifacts,
        )

        async with pool.acquire() as conn:
            model_artifacts = await get_model_artifacts(
                conn, filter_model_ids, providers=True
            )
        pids: set[UUID] = set()
        for m in model_artifacts:
            pids.update(m.provider_ids or [])
        if pids:
            provider_resource_ids = list(pids)
        else:
            return _empty_response(actor_name)

    # ── Step 3: Search providers ────────────────────────────────────────

    # Status filter → active_only flag + optional post-filter
    active_only = True
    inactive_only = False
    if filter_status:
        has_active = any(s.lower() in ("active", "true") for s in filter_status)
        has_inactive = any(s.lower() in ("inactive", "false") for s in filter_status)
        if has_active and not has_inactive:
            active_only = True
        elif has_inactive and not has_active:
            active_only = False
            inactive_only = True
        else:
            # Both selected or empty — show all
            active_only = False

    async with pool.acquire() as conn:
        provider_ids_list, total_count = await search_providers(
            conn,
            search=search,
            department_ids=filter_department_ids,
            provider_ids=provider_resource_ids,
            active_only=active_only,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not provider_ids_list:
        return _empty_response(actor_name, total_count=0)

    # ── Step 4: Get provider artifacts with junction IDs ────────────────

    async with pool.acquire() as conn:
        all_artifacts = await get_providers(
            conn,
            provider_ids_list,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            values=True,
            providers=True,
        )

    # Post-filter for inactive_only (search tool only supports active_only)
    if inactive_only:
        artifacts = [a for a in all_artifacts if not a.active]
    else:
        artifacts = all_artifacts

    if not artifacts:
        return _empty_response(actor_name, total_count=0)

    # ── Step 5: Parallel hydration + facets ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_value_ids: list[UUID] = []
    all_provider_resource_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_value_ids.extend(a.value_ids or [])
        all_provider_resource_ids.extend(a.provider_ids or [])

    async def _fetch_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_values() -> list:
        async with pool.acquire() as conn:
            return await get_values(conn, all_value_ids, redis)

    async def _fetch_providers_resource() -> list:
        async with pool.acquire() as conn:
            return await get_providers_resource(conn, all_provider_resource_ids, redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, provider=True, limit_count=100
            )

    async def _fetch_model_facet() -> list:
        async with pool.acquire() as conn:
            return await search_models_resource(
                conn, redis, search=model_search, limit_count=100
            )

    (
        names_data,
        descriptions_data,
        values_data,
        providers_resource_data,
        department_facet,
        model_facet,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty_list(),
        _fetch_descriptions() if all_description_ids else _empty_list(),
        _fetch_values() if all_value_ids else _empty_list(),
        _fetch_providers_resource() if all_provider_resource_ids else _empty_list(),
        # Facets
        _fetch_department_facet(),
        _fetch_model_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    value_map = {v.id: v for v in values_data}

    # Count active models per provider using provider_resource data
    # provider_resource has provider_id field which maps to artifacts
    provider_resource_map = {p.id: p for p in providers_resource_data}

    # ── Step 6: Build provider list with permissions ────────────────────

    # To count active models, use model_facet data: each model_resource has provider_id
    provider_model_counts: dict[UUID, int] = {}
    for m in model_facet:
        if m.provider_id:
            for a in artifacts:
                for prid in a.provider_ids or []:
                    pr = provider_resource_map.get(prid)
                    if pr and m.provider_id == pr.id:
                        provider_model_counts[a.id] = (
                            provider_model_counts.get(a.id, 0) + 1
                        )

    providers_list: list[ListProviderApiProvider] = []

    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )
        value_obj = value_map.get(a.value_ids[0]) if a.value_ids else None

        dept_ids = list(a.department_ids or [])
        active_model_count = provider_model_counts.get(a.id, 0)

        can_edit = compute_can_edit(
            user_role=user_role,
            provider_department_ids=dept_ids,
            active_model_count=active_model_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            provider_department_ids=[str(d) for d in dept_ids],
            active_model_count=active_model_count,
        )
        can_duplicate = compute_can_duplicate(user_role=user_role)

        providers_list.append(
            ListProviderApiProvider(
                provider_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                value=value_obj.value if value_obj else None,
                active=a.active,
                updated_at=a.updated_at,
                department_ids=dept_ids,
                model_usage_count=active_model_count,
                model_ids=None,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
            )
        )

    # ── Step 7: Build facet sections ───────────────────────────────────

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

    model_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(m.id), name=m.name, count=0) for m in model_facet
        ],
        selected_ids=[str(mid) for mid in filter_model_ids]
        if filter_model_ids
        else None,
        search=model_search,
    )

    status_filter = ListFilterSection(
        options=[
            ListFilterOption(id="active", name="Active", count=0),
            ListFilterOption(id="inactive", name="Inactive", count=0),
        ],
        selected_ids=filter_status if filter_status else None,
    )

    return ListProviderApiResponse(
        actor_name=actor_name,
        providers=providers_list,
        department_filter=department_filter,
        model_filter=model_filter,
        status_filter=status_filter,
        total_count=total_count,
    )


# ── Helpers ────────────────────────────────────────────────────────────


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListProviderApiResponse:
    return ListProviderApiResponse(
        actor_name=actor_name,
        providers=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
