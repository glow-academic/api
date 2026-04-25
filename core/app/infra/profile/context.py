"""Resolve profile artifact context — merged junctions + hydrated resources."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.flag_icons import hydrate_flag_icons
from app.infra.types import ArtifactContext, ResourcePair
from app.tools.artifacts.profile.get import get_profiles as get_profile_artifacts
from app.tools.entries.profile_drafts.get import get_profile_drafts
from app.tools.resources.departments.get import get_departments
from app.tools.resources.departments.search import search_departments
from app.tools.resources.emails.get import get_emails
from app.tools.resources.emails.search import search_emails
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.names.search import search_names
from app.tools.resources.roles.get import get_roles
from app.tools.resources.permissions.search import search_permissions
from app.tools.resources.request_limits.search import search_request_limits
from app.tools.resources.roles.search import search_roles

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

PROFILE_FLAG_TYPES = {"profile_active"}


@dataclass
class _MergedIds:
    name_ids: list[UUID]
    email_ids: list[UUID]
    flag_ids: list[UUID]
    department_ids: list[UUID]
    role_ids: list[UUID]


def _merge_junction_ids(artifact, draft) -> _MergedIds:
    name_ids = list(artifact.name_ids or []) if artifact else []
    email_ids = list(artifact.email_ids or []) if artifact else []
    flag_ids = list(artifact.flag_ids or []) if artifact else []
    department_ids = list(artifact.department_ids or []) if artifact else []
    role_ids = list(artifact.role_ids or []) if artifact else []

    if draft:
        if draft.name_ids:
            name_ids = list(draft.name_ids)
        if draft.email_ids:
            email_ids = list(draft.email_ids)
        if draft.flag_ids:
            flag_ids = list(draft.flag_ids)
        if draft.department_ids:
            department_ids = list(draft.department_ids)
        if draft.role_ids:
            role_ids = list(draft.role_ids)

    return _MergedIds(
        name_ids=name_ids,
        email_ids=email_ids,
        flag_ids=flag_ids,
        department_ids=department_ids,
        role_ids=role_ids,
    )


async def resolve_profile_context(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID | None,
    group_id: UUID,
    draft_id: UUID | None = None,
    user_department_ids: list[UUID] | None = None,
    names_search: str | None = None,
    emails_search: str | None = None,
    flags_search: str | None = None,
    departments_search: str | None = None,
    roles_search: str | None = None,
    names_limit: int | None = None,
    emails_limit: int | None = None,
    flags_limit: int | None = None,
    departments_limit: int | None = None,
    roles_limit: int | None = None,
    names_selected_only: bool | None = None,
    emails_selected_only: bool | None = None,
    flags_selected_only: bool | None = None,
    departments_selected_only: bool | None = None,
    roles_selected_only: bool | None = None,
    bypass_cache: bool = False,
) -> ArtifactContext:
    """Resolve a profile artifact into fully hydrated resources."""

    user_dept_ids = user_department_ids or []

    async def _fetch_artifact() -> list:
        if not profile_id:
            return []
        async with pool.acquire() as conn:
            return await get_profile_artifacts(
                conn,
                [profile_id],
                active=None,
                names=True,
                departments=True,
                flags=True,
                emails=True,
                roles=True,
            )

    async def _fetch_draft() -> list:
        if not draft_id:
            return []
        async with pool.acquire() as conn:
            return await get_profile_drafts(conn, [draft_id])

    artifacts, drafts = await asyncio.gather(_fetch_artifact(), _fetch_draft())
    artifact = artifacts[0] if artifacts else None
    draft = drafts[0] if drafts else None
    merged = _merge_junction_ids(artifact, draft)
    active = artifact.active if artifact else True

    async def _get_names() -> list:
        return await get_names(pool, merged.name_ids, redis, bypass_cache)

    async def _search_names() -> list:
        async with pool.acquire() as conn:
            return await search_names(
                conn,
                redis,
                search=names_search,
                limit_count=names_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if names_selected_only else "all",
                exclude_ids=merged.name_ids,
                bypass_cache=bypass_cache,
                profile=True,
            )

    async def _get_emails() -> list:
        return await get_emails(pool, merged.email_ids, redis, bypass_cache)

    async def _search_emails() -> list:
        async with pool.acquire() as conn:
            return await search_emails(
                conn,
                redis,
                search=emails_search,
                limit_count=emails_limit or 20,
                exclude_ids=merged.email_ids,
                bypass_cache=bypass_cache,
                profile=True,
            )

    async def _get_flags() -> list:
        return await get_flags(pool, merged.flag_ids, redis, bypass_cache)

    async def _search_flags() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn,
                redis,
                search=flags_search,
                limit_count=flags_limit or 200,
                exclude_ids=merged.flag_ids,
                flag_type="profile_active",
                bypass_cache=bypass_cache,
                profile=True,
            )

    async def _get_departments() -> list:
        return await get_departments(pool, merged.department_ids, redis, bypass_cache)

    async def _search_departments() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn,
                redis,
                search=departments_search,
                limit_count=departments_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if departments_selected_only else ("all" if profile_id is None else "recent"),
                exclude_ids=merged.department_ids,
                department_ids=user_dept_ids,
                bypass_cache=bypass_cache,
                profile=True,
            )

    async def _get_roles() -> list:
        return await get_roles(pool, merged.role_ids, redis, bypass_cache)

    async def _search_roles() -> list:
        async with pool.acquire() as conn:
            return await search_roles(
                conn,
                redis,
                search=roles_search,
                limit_count=roles_limit or 20,
                draft_id=group_id,
                suggest_source="selected" if roles_selected_only else "all",
                exclude_ids=merged.role_ids,
                bypass_cache=bypass_cache,
                profile=True,
            )

    async def _search_permissions_catalog() -> list:
        # Full permissions catalog so the role editor can render the
        # artifact × operation grid client-side.
        async with pool.acquire() as conn:
            return await search_permissions(
                conn,
                redis,
                search=None,
                limit_count=1000,
                bypass_cache=bypass_cache,
            )

    async def _search_request_limits_catalog() -> list:
        async with pool.acquire() as conn:
            return await search_request_limits(
                conn,
                redis,
                search=None,
                limit_count=200,
                bypass_cache=bypass_cache,
            )

    (
        names_selected,
        names_suggestions,
        emails_selected,
        emails_suggestions,
        flags_selected,
        flags_suggestions,
        departments_selected,
        departments_suggestions,
        roles_selected,
        roles_suggestions,
        permissions_catalog,
        request_limits_catalog,
    ) = await asyncio.gather(
        _get_names(),
        _search_names(),
        _get_emails(),
        _search_emails(),
        _get_flags(),
        _search_flags(),
        _get_departments(),
        _search_departments(),
        _get_roles(),
        _search_roles(),
        _search_permissions_catalog(),
        _search_request_limits_catalog(),
    )

    filtered_flag_suggestions = [
        flag for flag in flags_suggestions if getattr(flag, "type", None) in PROFILE_FLAG_TYPES
    ]

    pending_ids: set[UUID] = set()
    if draft:
        pending_ids.update(draft.pending_name_ids or [])
        pending_ids.update(draft.pending_email_ids or [])
        pending_ids.update(draft.pending_flag_ids or [])
        pending_ids.update(draft.pending_department_ids or [])
        pending_ids.update(draft.pending_role_ids or [])

    # Hydrate SVG icons onto each flag (icon_id → icon markup).
    async with pool.acquire() as conn:
        await hydrate_flag_icons(
            list(flags_selected) + list(filtered_flag_suggestions), conn, redis, bypass_cache
        )

    return ArtifactContext(
        artifact_id=artifact.id if artifact else None,
        active=active,
        group_id=group_id,
        resources={
            "names": ResourcePair(selected=names_selected, suggestions=names_suggestions),
            "emails": ResourcePair(selected=emails_selected, suggestions=emails_suggestions),
            "flags": ResourcePair(selected=flags_selected, suggestions=filtered_flag_suggestions),
            "departments": ResourcePair(
                selected=departments_selected,
                suggestions=departments_suggestions,
            ),
            "roles": ResourcePair(selected=roles_selected, suggestions=roles_suggestions),
        },
        entries={
            "pending_ids": pending_ids,
            "permissions": permissions_catalog,
            "request_limits": request_limits_catalog,
        },
    )


async def context_profile_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
    is_emulation: bool = False,
    emulation_depth: int = 0,
) -> 'ProfileContextApiResponse':
    """profile context — big-cache wrapped."""
    from app.infra.profile.types import ProfileContextApiResponse

    return await get_or_build(
        redis=redis,
        key=big_cache_key("profile/context", {
            "profile_id": str(profile_id),
            "session_id": str(session_id) if session_id else None,
            "is_emulation": is_emulation,
            "emulation_depth": emulation_depth,
        }),
        tags=["context", "profile", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ProfileContextApiResponse,
        builder=lambda: _context_profile_build(
            pool, redis,
            profile_id=profile_id,
            session_id=session_id,
            bypass_cache=bypass_cache,
            is_emulation=is_emulation,
            emulation_depth=emulation_depth,
        ),
        bypass_cache=bypass_cache,
    )


async def _context_profile_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    bypass_cache: bool = False,
    is_emulation: bool = False,
    emulation_depth: int = 0,
) -> "ProfileContextApiResponse":
    """Resolve profile identity, permissions, and theme for the context endpoint."""

    from app.infra.identity.settings import resolve_settings_theme
    from app.infra.identity.simulatable import SIMULATABLE_ROLES
    from app.infra.profile.types import ProfileContextApiResponse, ThemePrimitives
    from app.infra.profile_identity_context import resolve_profile_identity_context
    from app.infra.shared_types import QGetProfileContextV4RoleResource

    identity = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        bypass_cache=bypass_cache,
        session_id=session_id,
    )
    if not identity:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Profile not found")

    scoped_roles = sorted(SIMULATABLE_ROLES.get(identity.role, set()))

    async def _fetch_roles() -> list:
        return await get_roles(pool, None, redis, bypass_cache=bypass_cache)

    async def _fetch_theme() -> ThemePrimitives | None:
        if not identity.settings_id:
            return None
        theme = await resolve_settings_theme(
            pool,
            redis,
            identity.settings_id,
            bypass_cache=bypass_cache,
        )
        if not theme or not theme.is_active or not theme.primary_color:
            return None
        return ThemePrimitives(
            primary=theme.primary_color,
            accent=theme.accent,
            background=theme.background,
            surface=theme.surface,
            success=theme.success,
            warning=theme.warning,
            error=theme.error,
            chart1=theme.chart1,
            chart2=theme.chart2,
            chart3=theme.chart3,
            chart4=theme.chart4,
            chart5=theme.chart5,
        )

    roles_raw, theme = await asyncio.gather(_fetch_roles(), _fetch_theme())

    role_resources = [
        QGetProfileContextV4RoleResource(
            role=role.name,
            name=role.name,
            description=role.description,
            icon_value=None,
            color_hex=None,
        )
        for role in roles_raw
    ]

    return ProfileContextApiResponse(
        id=profile_id,
        name=identity.name,
        role=identity.role,
        active=identity.is_active,
        role_artifacts=identity.role_artifacts,
        scoped_roles=scoped_roles,
        department_ids=[str(department_id) for department_id in identity.department_ids],
        primary_department_id=str(identity.primary_department_id)
        if identity.primary_department_id
        else None,
        settings_id=str(identity.settings_id) if identity.settings_id else None,
        theme=theme,
        session_id=identity.session_id,
        is_emulation=is_emulation or None,
        emulation_depth=emulation_depth or None,
        role_resources=role_resources,
    )
