"""Hydrate ``ListSettingApiSetting`` rows for a specific set of setting ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_setting_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names/
descriptions → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.setting.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.setting.types import ListSettingApiSetting
from app.tools.artifacts.setting.get import get_settings
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names


async def hydrate_setting_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    setting_ids: list[UUID],
) -> list[ListSettingApiSetting]:
    """Return ``ListSettingApiSetting`` rows for the given setting ids.

    Mirrors ``_search_setting_build``'s row-hydration steps minus
    facets and pagination. Active scenario / usage counts aren't part
    of setting rows, so the row is fully self-contained.
    """
    if not setting_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

    async with pool.acquire() as conn:
        artifacts = await get_settings(
            conn,
            setting_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            providers=True,
            auths=True,
            systems=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="setting", artifact_ids=setting_ids,
            limit=len(setting_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _descs() -> list:
        return (
            await get_descriptions(pool, all_description_ids, redis)
            if all_description_ids
            else []
        )

    names_data, descriptions_data = await asyncio.gather(_names(), _descs())

    name_map = {n.id: n for n in names_data}
    description_map = {d.id: d for d in descriptions_data}

    rows: list[ListSettingApiSetting] = []
    for a in artifacts:
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        desc_obj = (
            description_map.get(a.description_ids[0]) if a.description_ids else None
        )

        dept_ids_str = [str(d) for d in (a.department_ids or [])]

        can_edit = compute_can_edit(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            setting_department_ids=dept_ids_str,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
            setting_department_ids=dept_ids_str,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level,
            role_permissions=profile.role_permissions,
        )

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListSettingApiSetting(
                settings_id=a.id,
                created_at=a.created_at,
                active=a.active,
                is_inactive=not a.active,
                name=name_obj.name if name_obj else None,
                description=desc_obj.description if desc_obj else None,
                department_ids=dept_ids_str,
                provider_ids=list(a.provider_ids or []),
                auth_ids=list(a.auth_ids or []),
                system_ids=list(a.systems_ids or []),
                can_edit=can_edit,
                can_delete=can_delete,
                can_duplicate=can_duplicate,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    return rows
