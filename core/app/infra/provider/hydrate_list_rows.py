"""Hydrate ``ListProviderApiProvider`` rows for a specific set of provider ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_provider_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions / values → compute permissions), without the facet
aggregation, pagination, or big-cache wrap that the search route layers
on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.provider.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.provider.types import ListProviderApiProvider
from app.tools.artifacts.model.search import search_models
from app.tools.artifacts.provider.get import get_providers
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.values.get import get_values


async def hydrate_provider_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    provider_ids: list[UUID],
) -> list[ListProviderApiProvider]:
    """Return ``ListProviderApiProvider`` rows for the given provider ids.

    Mirrors ``_search_provider_build``'s row-hydration steps minus
    facets and pagination. ``model_usage_count`` is computed via the
    same ``search_models(provider_ids=..., active_only=True)`` call
    that ``resolve_provider_permissions_context`` uses, so it stays
    accurate for both fresh and updated rows.
    """
    if not provider_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_providers(
            conn,
            provider_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            values=True,
            providers=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="provider", artifact_ids=provider_ids,
            limit=len(provider_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_value_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        if a.value_id:
            all_value_ids.append(a.value_id)

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return await get_descriptions(pool, all_description_ids, redis) if all_description_ids else []

    async def _values() -> list:
        return await get_values(pool, all_value_ids, redis) if all_value_ids else []

    async def _model_counts() -> dict[UUID, int]:
        # Per-row active model count (same predicate
        # ``resolve_provider_permissions_context`` uses for can_edit /
        # can_delete). One query per provider id is fine here — the
        # set is small (just the rows touched by this op).
        counts: dict[UUID, int] = {}
        async with pool.acquire() as conn:
            for pid in provider_ids:
                _, total = await search_models(
                    conn,
                    provider_ids=[pid],
                    active_only=True,
                    limit_count=1,
                )
                counts[pid] = total
        return counts

    names_data, descriptions_data, values_data, model_counts = await asyncio.gather(
        _names(), _descs(), _values(), _model_counts(),
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    value_map = {v.id: v for v in values_data}

    rows: list[ListProviderApiProvider] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None
        value_obj = value_map.get(a.value_id) if a.value_id else None

        dept_ids = list(a.department_ids or [])
        active_model_count = model_counts.get(a.id, 0)

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            provider_department_ids=dept_ids,
            active_model_count=active_model_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            provider_department_ids=[str(d) for d in dept_ids],
            active_model_count=active_model_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListProviderApiProvider(
                provider_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                value=value_obj.value if value_obj else None,
                active=a.active,
                is_inactive=not a.active,
                updated_at=a.updated_at,
                department_ids=dept_ids,
                model_usage_count=active_model_count,
                model_ids=None,
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    return rows
