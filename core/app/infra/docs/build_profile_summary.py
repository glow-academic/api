"""Build a fully-hydrated ProfileSummary from a ProfileIdentityContext.

Centralises the logic that was previously duplicated across 33 page_context
files and adds the new fields needed to replace /profiles/context.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.types import ProfileSummary
from app.infra.profile.types import ThemePrimitives
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.shared_types import QGetProfileContextV4RoleResource


async def build_profile_summary(
    pool: asyncpg.Pool,
    redis: Redis,
    profile: ProfileIdentityContext,
    *,
    is_emulation: bool = False,
) -> ProfileSummary:
    """Build a full ProfileSummary with theme + role resources + scoped roles."""
    from app.infra.identity.settings import resolve_settings_theme
    from app.infra.identity.simulatable import SIMULATABLE_ROLES
    from app.tools.resources.roles.get import get_roles

    # --- Parallel fetches: theme + roles ---

    async def _fetch_theme() -> ThemePrimitives | None:
        if not profile.settings_id:
            return None
        theme = await resolve_settings_theme(
            pool, redis, profile.settings_id,
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

    async def _fetch_roles() -> list:
        async with pool.acquire() as c:
            return await get_roles(c, None, redis)

    theme, roles_raw = await asyncio.gather(_fetch_theme(), _fetch_roles())

    role_resources = [
        QGetProfileContextV4RoleResource(
            role=r.name,
            name=r.name,
            description=r.description,
            icon_value=None,
            color_hex=None,
        )
        for r in roles_raw
    ]

    scoped_roles = sorted(SIMULATABLE_ROLES.get(profile.role, set()))

    return ProfileSummary(
        id=profile.profiles_id,
        name=profile.name,
        role=profile.role,
        role_level=profile.role_level,
        department_ids=profile.department_ids,
        artifact_access=profile.role_artifacts,
        role_permissions=profile.role_permissions,
        is_active=profile.is_active,
        active=profile.is_active,
        theme=theme,
        group_id=profile.group_id,
        session_id=profile.session_id,
        is_emulation=is_emulation,
        role_resources=role_resources,
        scoped_roles=scoped_roles,
    )
