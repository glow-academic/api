"""Build a fully-hydrated ProfileSummary from a ProfileIdentityContext.

Centralises the logic that was previously duplicated across 33 page_context
files and adds the new fields needed to replace /profiles/context.
"""

from __future__ import annotations

import asyncio

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.types import ProfileSummary
from app.infra.profile.types import ThemeBundle, Thresholds
from app.infra.profile_identity_context import ProfileIdentityContext
from app.infra.shared_types import QGetProfileContextV4RoleResource
from app.utils.settings.theme import derive_theme_tokens


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

    async def _fetch_theme() -> ThemeBundle | None:
        if not profile.settings_id:
            return None
        theme = await resolve_settings_theme(
            pool, redis, profile.settings_id,
        )
        # `theme.light.primary` plays the role of "any palette configured?"
        # — if a setting is active but seeds zero colors, we still want to
        # short-circuit to globals.css defaults rather than send a useless
        # all-empty bundle.
        if not theme or not theme.is_active or not theme.light.primary:
            return None

        light_tokens = derive_theme_tokens(theme.light)
        dark_tokens = derive_theme_tokens(theme.dark)

        # Fall back to canonical defaults (85/80/70) when a threshold row
        # is missing — mirrors resolve_thresholds.
        thresholds = Thresholds(
            success=theme.success_threshold if theme.success_threshold is not None else 85,
            warning=theme.warning_threshold if theme.warning_threshold is not None else 80,
            danger=theme.danger_threshold if theme.danger_threshold is not None else 70,
        )
        return ThemeBundle(
            primitives=theme.light,
            tokens=light_tokens,
            dark_primitives=theme.dark,
            dark_tokens=dark_tokens,
            thresholds=thresholds,
        )

    async def _fetch_roles() -> list:
        return await get_roles(pool, None, redis)

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
        session_id=profile.session_id,
        is_emulation=is_emulation,
        role_resources=role_resources,
        scoped_roles=scoped_roles,
    )
