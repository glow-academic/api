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

from app.infra.profile.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.profile.types import (
    ListProfilesApiProfile,
    ListProfilesApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.profile.get import get_profiles
from app.tools.artifacts.profile.search import search_profiles
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.get import (
    get_profiles as get_profiles_resource,
)
from app.tools.resources.request_limits.get import get_request_limits
from app.tools.resources.roles.get import get_roles
from app.tools.resources.roles.search import search_roles


async def search_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
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

    actor_profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if actor_profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = actor_profile.role
    user_department_ids = actor_profile.department_ids
    actor_name = actor_profile.name

    # -- Step 2: Scope by role hierarchy + optional role_filter --
    # Visible roles: roles at or below the requester's level
    VISIBLE_ROLES: dict[str, set[str]] = {
        "superadmin": {"superadmin", "admin", "instructional", "member", "guest"},
        "admin": {"admin", "instructional", "member", "guest"},
        "instructional": {"instructional", "member", "guest"},
        "member": {"member", "guest"},
        "guest": {"guest"},
    }
    visible = VISIBLE_ROLES.get(user_role, set())

    async with pool.acquire() as conn:
        all_roles = await get_roles(conn, None, redis)

        # Start with hierarchy-scoped roles
        allowed_roles = {r.role for r in all_roles if r.role in visible}

        # Intersect with explicit role_filter if provided
        if role_filter:
            if role_filter in allowed_roles:
                allowed_roles = {role_filter}
            else:
                return _empty_response(actor_name, total_count=0)

        role_ids_filter = [r.id for r in all_roles if r.role in allowed_roles]
        if not role_ids_filter:
            return _empty_response(actor_name, total_count=0)

        # -- Step 3: Search profiles (always exclude self) --

        profile_ids, total_count = await search_profiles(
            conn,
            search=search,
            department_ids=filter_department_ids,
            cohort_ids=cohort_ids,
            role_ids=role_ids_filter,
            exclude_ids=[profile_id],
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
            request_limits=True,
            roles=True,
        )

    # -- Step 5: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_email_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_role_ids: list[UUID] = []
    all_request_limit_ids: list[UUID] = []
    all_profile_resource_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_email_ids.extend(a.email_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_role_ids.extend(a.role_ids or [])
        all_request_limit_ids.extend(a.request_limit_ids or [])
        all_profile_resource_ids.extend(a.profile_ids or [])

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

    async def _fetch_request_limits() -> list:
        async with pool.acquire() as conn:
            return await get_request_limits(conn, all_request_limit_ids, redis)

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

    (
        names_data,
        emails_data,
        departments_data,
        roles_data,
        request_limits_data,
        profiles_resource_data,
        department_facet,
        role_facet,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty_list(),
        _fetch_emails() if all_email_ids else _empty_list(),
        _fetch_departments() if all_department_ids else _empty_list(),
        _fetch_roles() if all_role_ids else _empty_list(),
        _fetch_request_limits() if all_request_limit_ids else _empty_list(),
        _fetch_profiles_resource() if all_profile_resource_ids else _empty_list(),
        _fetch_department_facet(),
        _fetch_role_facet(),
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    email_map = {e.id: e for e in emails_data}
    dept_map = {d.id: d for d in departments_data}
    role_map = {r.id: r for r in roles_data}
    request_limit_map = {rl.id: rl for rl in request_limits_data}
    profile_resource_map = {p.id: p for p in profiles_resource_data}

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
        if a.role_ids:
            role_obj = role_map.get(a.role_ids[0])
            if role_obj:
                target_role = role_obj.role

        # Resolve departments
        dept_ids_str: list[str] = []
        primary_department_id: str | None = None
        for did in a.department_ids or []:
            dept = dept_map.get(did)
            if dept:
                dept_ids_str.append(str(dept.id))
                if dept.is_primary:
                    primary_department_id = str(dept.id)

        # Resolve requests_per_day from profiles_resource
        requests_per_day: int | None = None
        if a.profile_ids:
            prof_resource = profile_resource_map.get(a.profile_ids[0])
            if prof_resource:
                requests_per_day = prof_resource.requests_per_day

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
            user_role=user_role,
            target_is_self=target_is_self,
            target_department_ids=None,
            target_role=target_role,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            target_is_self=target_is_self,
            target_role=target_role,
        )
        can_duplicate = compute_can_duplicate(user_role)

        profiles_list.append(
            ListProfilesApiProfile(
                profile_id=a.id,
                emails=profile_emails if profile_emails else None,
                primary_email=primary_email,
                name=name,
                role=target_role,
                initials=initials,
                department_ids=dept_ids_str if dept_ids_str else None,
                primary_department_id=primary_department_id,
                requests_per_day=requests_per_day,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
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
            ListFilterOption(id=str(r.role), name=r.name, count=0) for r in role_facet
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
