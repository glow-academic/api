"""Hydrate `ListModelApiModel` rows for a specific set of model ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_model_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate resources
→ compute permissions), without the facet aggregation, pagination, or
big-cache wrap that the search route layers on top.

Note: model has no ``filter_agent_ids`` reverse-lookup needed here —
the hydrator works from explicit model_ids only. The bulk-write
``resolve_matching_model_ids`` performs that hop (agents → models)
before bulk update; here we just get full rows for already-resolved
model artifact ids. The reverse-lookup hop the recipe references is
the agent → models hop that lives in ``resolve_matching_ids.py``.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.model.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.model.types import ListModelApiModel
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.model.get import get_models
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.providers.get import (
    get_providers as get_providers_resource,
)


async def hydrate_model_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    model_ids: list[UUID],
) -> list[ListModelApiModel]:
    """Return ``ListModelApiModel`` rows for the given model ids.

    Mirrors ``_search_model_build``'s row-hydration steps minus facets
    and pagination. Permissions are computed via the same helpers the
    list endpoint uses; ``active_agent_count`` is resolved for all rows
    in a single grouped junction query (see below) so can_edit/can_delete
    reflect current state without an N+1.
    """
    if not model_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_models(
            conn,
            model_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            providers=True,
            models=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, redis, artifact="model", artifact_ids=model_ids,
            limit=len(model_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_provider_resource_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        if a.provider_id:
            all_provider_resource_ids.append(a.provider_id)

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return await get_descriptions(pool, all_description_ids, redis) if all_description_ids else []

    async def _providers() -> list:
        if not all_provider_resource_ids:
            return []
        async with pool.acquire() as conn:
            return await get_providers_resource(conn, all_provider_resource_ids, redis)

    names_data, descriptions_data, providers_data = await asyncio.gather(
        _names(), _descs(), _providers(),
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}
    provider_resource_map = {p.id: p for p in providers_data}

    # Reverse lookup: model artifact -> active agent count, via the same
    # hop the bulk-write resolver uses (model artifact has ``model_ids``
    # carrying its models_resource ids; agents reference those
    # models_resource ids in their junction). Mirrors
    # ``resolve_model_permissions_context`` so can_edit/can_delete are
    # correct on freshly-created/updated rows.
    #
    # Batched: one grouped query over EVERY model's resource ids instead
    # of one ``search_agents`` round-trip per row. The bulk-write paths
    # (create/duplicate/update all-matching) hydrate N rows at once, so a
    # per-row query was N+1. The query mirrors ``search_agents``'s
    # active-agent semantics (active junction → active agent_artifact),
    # returning (agent_id, models_id) pairs so the per-model count
    # de-dupes agents linked to multiple of a model's resource ids —
    # identical to ``search_agents``'s DISTINCT-agent total.
    all_model_resource_ids: list[UUID] = []
    for a in artifacts:
        all_model_resource_ids.extend(a.model_ids or [])

    agents_by_model_resource: dict[UUID, set[UUID]] = {}
    if all_model_resource_ids:
        async with pool.acquire() as conn:
            pair_rows = await conn.fetch(
                """
                SELECT DISTINCT amj.models_id, amj.agent_id
                FROM agent_models_junction amj
                JOIN agent_artifact a ON a.id = amj.agent_id AND a.active = true
                WHERE amj.models_id = ANY($1) AND amj.active = true
                """,
                all_model_resource_ids,
            )
        for pr in pair_rows:
            agents_by_model_resource.setdefault(pr["models_id"], set()).add(
                pr["agent_id"]
            )

    def _agent_count(model_resource_ids: list[UUID]) -> int:
        if not model_resource_ids:
            return 0
        agents: set[UUID] = set()
        for rid in model_resource_ids:
            agents |= agents_by_model_resource.get(rid, set())
        return len(agents)

    rows: list[ListModelApiModel] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None

        provider_id: UUID | None = None
        provider_name: str | None = None
        base_url: str | None = None
        if a.provider_id:
            pr = provider_resource_map.get(a.provider_id)
            if pr:
                provider_id = pr.id
                provider_name = pr.name
                base_url = pr.endpoint or ""

        dept_ids = [str(d) for d in (a.department_ids or [])]

        active_agent_count = _agent_count(list(a.model_ids or []))

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            model_department_ids=dept_ids,
            active_agent_count=active_agent_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            model_department_ids=dept_ids,
            active_agent_count=active_agent_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListModelApiModel(
                id=a.id,

                model_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                provider_id=provider_id,
                provider_name=provider_name,
                base_url=base_url,
                department_ids=dept_ids,
                is_inactive=not a.active,
                active=a.active,
                image_model=None,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    return rows
