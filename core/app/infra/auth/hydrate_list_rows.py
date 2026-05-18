"""Hydrate ``ListAuthApiAuth`` rows for a specific set of auth ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_auth_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
descriptions → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
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
from app.infra.auth.types import ListAuthApiAuth
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.auth.get import get_auths
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names


async def hydrate_auth_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    auth_ids: list[UUID],
) -> list[ListAuthApiAuth]:
    """Return ``ListAuthApiAuth`` rows for the given auth ids.

    Mirrors ``_search_auth_build``'s row-hydration steps minus facets
    and pagination. ``setting_ids`` and ``auth_item_key_ids`` are
    resolved via the same junction queries the search route uses, so
    a freshly-created/updated auth shows correct cross-references on
    the client's ghost rail without an SSR refresh.
    """
    if not auth_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level

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
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="auth", artifact_ids=auth_ids,
            limit=len(auth_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_auth_resource_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_auth_resource_ids.extend(a.auth_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as c:
            return await get_descriptions(c, all_description_ids, redis)

    async def _settings_by_auth_resource() -> dict[UUID, list[UUID]]:
        # Setting artifact ids that reference any of this auth's
        # auths_resource rows via setting_auths_junction. Mirrors the
        # query in ``_search_auth_build``.
        if not all_auth_resource_ids:
            return {}
        async with pool.acquire() as c:
            rows = await c.fetch(
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
        return {r["auths_id"]: list(r["setting_ids"] or []) for r in rows}

    async def _auth_item_keys_by_auth() -> dict[UUID, list[UUID]]:
        # auth_item_keys_resource rows owned by this auth_artifact via
        # auth_item_keys_resource.auth_id. Mirrors the search query.
        async with pool.acquire() as c:
            rows = await c.fetch(
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
        return {r["auth_id"]: list(r["key_ids"] or []) for r in rows}

    async def _perm(artifact_id: UUID) -> AuthPermissionsContext:
        async with pool.acquire() as c:
            return await resolve_auth_permissions_context(c, artifact_id)

    perm_tasks = [_perm(a.id) for a in artifacts]

    (
        names_data,
        descriptions_data,
        settings_by_auth_resource,
        auth_item_keys_by_auth,
        *perm_results,
    ) = await asyncio.gather(
        _names(),
        _descs(),
        _settings_by_auth_resource(),
        _auth_item_keys_by_auth(),
        *perm_tasks,
    )

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListAuthApiAuth] = []
    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = description_map.get(a.description_ids[0]) if a.description_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_settings_count = perm_results[i].active_settings_count
        item_count = len(a.item_ids or [])

        # Aggregate setting_ids across this auth's auths_resource rows.
        auth_setting_ids: list[UUID] = []
        seen_setting_ids: set[UUID] = set()
        for ar_id in a.auth_ids or []:
            for sid in settings_by_auth_resource.get(ar_id, []):
                if sid not in seen_setting_ids:
                    seen_setting_ids.add(sid)
                    auth_setting_ids.append(sid)

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            active_settings_count=active_settings_count,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            active_settings_count=active_settings_count,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListAuthApiAuth(
                auth_id=a.id,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                item_count=item_count,
                department_ids=dept_ids_str,
                setting_ids=auth_setting_ids,
                auth_item_key_ids=list(auth_item_keys_by_auth.get(a.id, [])),
                is_inactive=is_inactive,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    return rows
