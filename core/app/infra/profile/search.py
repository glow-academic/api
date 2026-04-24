"""Profile search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_profiles — core artifact search (IDs + total_count)
  3. get_profiles — hydrate junction IDs
  4. Resource get tools — hydrate names, emails, roles, request_limits, departments
  5. Permissions — compute per-profile can_edit, can_delete, can_duplicate
  6. Facets — parallel resource searches for filter options
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
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.profile.types import (
    ListProfilesApiProfile,
    ListProfilesApiResponse,
)
from app.infra.api_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.profile.get import get_profiles
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.primary_departments.get import (
    get_primary_departments,
)
from app.tools.resources.profiles.get import (
    get_profiles as get_profiles_resource,
)
from app.tools.resources.roles.get import get_roles
from app.tools.resources.roles.search import search_roles


async def search_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    actor_profile_id: UUID | None = None,
    # Main filters
    search: str | None = None,
    cohort_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    role_filter: str | None = None,
    # Facet search text
    cohort_search: str | None = None,
    department_search: str | None = None,
    role_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListProfilesApiResponse:
    """Profile search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, departments, name
      2. Resolve role_filter -> role_ids for search tool
      3. search_profiles -> (profile_artifact_ids, total_count)
      4. get_profiles -> hydrate junction IDs
      5. Parallel: hydrate resources + facets
      6. Compute permissions per profile
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids
    actor_name = profile.name
    actor_role = profile.role

    # Resolve emulation chain once for is_emulated computation
    origin = actor_profile_id or profile_id
    chain = await resolve_emulation_chain(pool, origin)
    emulated_profile_ids: set[UUID] = {link.target_profile_id for link in chain}

    # -- Step 2: Scope by role hierarchy + optional role_filter --
    # Visible roles: roles at or below the requester's level (from DB).

    async with pool.acquire() as conn:
        all_roles = await get_roles(conn, None, redis)

        # Show roles at or below the user's level
        allowed_role_names = {r.name for r in all_roles if r.level >= user_role_level}

        # Intersect with explicit role_filter if provided
        if role_filter:
            if role_filter in allowed_role_names:
                allowed_role_names = {role_filter}
            else:
                return _empty_response(actor_name, total_count=0)

        role_ids_filter = [r.id for r in all_roles if r.name in allowed_role_names]
        if not role_ids_filter:
            return _empty_response(actor_name, total_count=0)

        # -- Step 3: Search profiles --

        profile_ids, total_count = await search_profiles(
            conn,
            search=search,
            department_ids=filter_department_ids,
            cohort_ids=cohort_ids,
            role_ids=role_ids_filter,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not profile_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 4: Get profile artifacts with junction IDs --

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
        )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_email_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_role_ids: list[UUID] = []
    all_profile_resource_ids: list[UUID] = []
    all_primary_department_resource_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_email_ids.extend(a.email_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_role_ids.extend(a.role_ids or [])
        all_profile_resource_ids.extend(a.profile_ids or [])
        all_primary_department_resource_ids.extend(a.primary_department_ids or [])

    async def _fetch_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_emails() -> list:
        async with pool.acquire() as conn:
            return await get_emails(conn, all_email_ids, redis)

    async def _fetch_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _fetch_roles() -> list:
        async with pool.acquire() as conn:
            return await get_roles(conn, all_role_ids, redis)

    async def _fetch_profiles_resource() -> list:
        async with pool.acquire() as conn:
            return await get_profiles_resource(conn, all_profile_resource_ids, redis)

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, profile=True, limit_count=100
            )

    async def _fetch_role_facet() -> list:
        async with pool.acquire() as conn:
            return await search_roles(
                conn, redis, search=role_search, profile=True, limit_count=100
            )

    async def _fetch_primary_departments() -> list:
        async with pool.acquire() as conn:
            return await get_primary_departments(
                conn, all_primary_department_resource_ids, redis
            )

    (
        names_data,
        emails_data,
        departments_data,
        roles_data,
        profiles_resource_data,
        department_facet,
        role_facet,
        primary_departments_data,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty_list(),
        _fetch_emails() if all_email_ids else _empty_list(),
        _fetch_departments() if all_department_ids else _empty_list(),
        _fetch_roles() if all_role_ids else _empty_list(),
        _fetch_profiles_resource() if all_profile_resource_ids else _empty_list(),
        _fetch_department_facet(),
        _fetch_role_facet(),
        _fetch_primary_departments() if all_primary_department_resource_ids else _empty_list(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    email_map = {e.id: e for e in emails_data}
    dept_map = {d.id: d for d in departments_data}
    role_map = {r.id: r for r in roles_data}
    profile_resource_map = {p.id: p for p in profiles_resource_data}
    # id -> departments_id (the actual department being marked primary)
    primary_department_map = {pd.id: pd.departments_id for pd in primary_departments_data}

    # -- Step 6: Build profile list with permissions --

    profiles_list: list[ListProfilesApiProfile] = []

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

        # Resolve role from roles_resource
        target_role: str | None = None
        target_role_name: str | None = None
        target_level: int | None = None
        if a.role_ids:
            role_obj = role_map.get(a.role_ids[0])
            if role_obj:
                target_role = role_obj.name
                target_role_name = role_obj.name
                target_level = role_obj.level

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
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)
        can_emulate = compute_can_emulate(
            actor_role=actor_role,
            target_role=target_role,
            target_is_self=target_is_self,
        )
        is_emulated = a.id in emulated_profile_ids

        profiles_list.append(
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
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                can_emulate=can_emulate,
                is_emulated=is_emulated,
            )
        )

    # -- Step 7: Build facet sections --

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

    role_filter_section = ListFilterSection(
        options=[
            ListFilterOption(id=str(r.name), name=r.name, count=0) for r in role_facet
        ],
        selected_ids=[role_filter] if role_filter else None,
        search=role_search,
    )

    return ListProfilesApiResponse(
        actor_name=actor_name,
        profiles=profiles_list,
        department_filter=department_filter,
        role_filter=role_filter_section,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListProfilesApiResponse:
    return ListProfilesApiResponse(
        actor_name=actor_name,
        profiles=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
