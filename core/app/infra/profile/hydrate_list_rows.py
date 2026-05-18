"""Hydrate ``ListProfilesApiProfile`` rows for a specific set of profile ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_profile_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names /
emails / roles / departments → compute permissions), without the facet
aggregation, pagination, or big-cache wrap that the search route layers
on top.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.identity.resolve_identity import resolve_emulation_chain
from app.infra.profile.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
    compute_can_emulate,
)
from app.infra.profile.types import ListProfilesApiProfile
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.profile.get import get_profiles
from app.tools.resources.departments.get import get_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.primary_departments.get import (
    get_primary_departments,
)
from app.tools.resources.roles.get import get_roles


async def hydrate_profile_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    profile_ids: list[UUID],
) -> list[ListProfilesApiProfile]:
    """Return ``ListProfilesApiProfile`` rows for the given profile ids.

    Mirrors ``_search_profile_build``'s row-hydration steps minus
    facets, pagination, and the big-cache wrap. ``role_filter`` would
    translate to ``role_ids`` in search, but here we hydrate concrete
    rows so the row's role is already determined by its junction; we
    only need ``get_roles`` for the role name/level/permissions.
    """
    if not profile_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids
    actor_role = profile.role

    # Resolve emulation chain once for is_emulated computation
    chain = await resolve_emulation_chain(pool, profile_id)
    emulated_profile_ids: set[UUID] = {link.target_profile_id for link in chain}

    async with pool.acquire() as conn:
        artifacts = await get_profiles(
            conn,
            profile_ids,
            names=True,
            departments=True,
            emails=True,
            profiles=True,
            roles=True,
            primary_departments=True,
            active=None,
        )

        from app.tools.entries.soft_calls.search import search_soft_calls
        ledger_entries = await search_soft_calls(
            conn, artifact="profile", artifact_ids=profile_ids,
            limit=len(profile_ids) or 1,
        )
    ledger_by_artifact_id = {e.artifact_id: e for e in ledger_entries}

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_email_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_role_ids: list[UUID] = []
    all_primary_department_resource_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_email_ids.extend(a.email_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_role_ids.extend(a.role_ids or [])
        all_primary_department_resource_ids.extend(a.primary_department_ids or [])

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _emails() -> list:
        return await get_emails(pool, all_email_ids, redis) if all_email_ids else []

    async def _departments() -> list:
        return await get_departments(pool, all_department_ids, redis) if all_department_ids else []

    async def _roles() -> list:
        return await get_roles(pool, all_role_ids, redis) if all_role_ids else []

    async def _primary_departments() -> list:
        return (
            await get_primary_departments(
                pool, all_primary_department_resource_ids, redis,
            )
            if all_primary_department_resource_ids
            else []
        )

    (
        names_data,
        emails_data,
        departments_data,
        roles_data,
        primary_departments_data,
    ) = await asyncio.gather(
        _names(), _emails(), _departments(), _roles(), _primary_departments(),
    )

    name_map = {n.id: n for n in names_data}
    email_map = {e.id: e for e in emails_data}
    dept_map = {d.id: d for d in departments_data}
    role_map = {r.id: r for r in roles_data}
    # id -> departments_id (the actual department being marked primary)
    primary_department_map = {pd.id: pd.departments_id for pd in primary_departments_data}

    rows: list[ListProfilesApiProfile] = []
    for a in artifacts:
        # Resolve name
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None
        name = name_obj.name if name_obj else None

        # Resolve emails
        profile_emails: list[str] = []
        primary_email: str | None = None
        for eid in a.email_ids or []:
            e = email_map.get(eid)
            if e and e.email:
                profile_emails.append(e.email)
                if e.is_primary:
                    primary_email = e.email

        # Resolve role from roles_resource (also yields permission_ids)
        target_role: str | None = None
        target_role_name: str | None = None
        target_level: int | None = None
        target_permission_ids: list[UUID] = []
        if a.role_ids:
            role_obj = role_map.get(a.role_ids[0])
            if role_obj:
                target_role = role_obj.name
                target_role_name = role_obj.name
                target_level = role_obj.level
                target_permission_ids = list(role_obj.permission_ids or [])

        # Resolve departments
        dept_ids_str: list[str] = []
        for did in a.department_ids or []:
            dept = dept_map.get(did)
            if dept:
                dept_ids_str.append(str(dept.id))

        # Primary department comes from the junction, not a per-dept flag.
        primary_department_id: str | None = None
        for pdr_id in a.primary_department_ids or []:
            target = primary_department_map.get(pdr_id)
            if target:
                primary_department_id = str(target)
                break

        # Compute initials from name
        initials: str | None = None
        if name:
            parts = name.strip().split()
            if len(parts) >= 2:
                initials = (parts[0][0] + parts[-1][0]).upper()
            elif parts:
                initials = parts[0][0].upper()

        # target_is_self: check if this artifact is the actor's profile
        target_is_self = a.id == profile_id

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            target_is_self=target_is_self,
            target_department_ids=a.department_ids or None,
            target_level=target_level,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            target_is_self=target_is_self,
            target_level=target_level,
        )
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )
        can_emulate = compute_can_emulate(
            actor_role=actor_role,
            target_role=target_role,
            target_is_self=target_is_self,
        )
        is_emulated = a.id in emulated_profile_ids

        ledger = ledger_by_artifact_id.get(a.id)
        rows.append(
            ListProfilesApiProfile(
                profile_id=a.id,
                emails=profile_emails if profile_emails else None,
                primary_email=primary_email,
                name=name,
                role=target_role,
                role_name=target_role_name,
                initials=initials,
                department_ids=dept_ids_str if dept_ids_str else None,
                primary_department_id=primary_department_id,
                permission_ids=target_permission_ids,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                can_emulate=can_emulate,
                is_emulated=is_emulated,
                is_inactive=not a.active,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
            )
        )

    return rows
