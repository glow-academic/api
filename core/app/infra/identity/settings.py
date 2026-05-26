"""Resolve settings theme — composes canonical black boxes.

Given a settings *resource* id (the canonical pointer carried on
``ProfileIdentityContext.settings_id``), fetches:
  1. Resource → artifact translation via ``search_settings`` (walks
     the ``setting_settings_junction`` black-box).
  2. Setting artifact with colors, thresholds, flags junctions.
  3. Colors, thresholds, flags resources in parallel.
  4. Maps by ``type`` in Python → light + dark ``ThemePrimitives`` + thresholds.

Color row ``type`` field is the canonical token name (snake_case):
``primary``, ``background``, ``card_foreground``, …, ``sidebar_ring``,
optionally prefixed with ``dark_`` for dark mode rows. So the resolver
just builds a ``{type: hex}`` map and dispatches by name.

No inline SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.artifacts.setting.search import search_settings
from app.tools.resources.colors.get import get_colors
from app.tools.resources.flags.get import get_flags
from app.tools.resources.thresholds.get import get_thresholds
from app.utils.settings.theme import ThemePrimitives


@dataclass(frozen=True)
class SettingsThemeResult:
    """Resolved theme data from a setting artifact."""

    is_active: bool
    light: ThemePrimitives = field(default_factory=ThemePrimitives)
    dark: ThemePrimitives = field(default_factory=ThemePrimitives)
    success_threshold: int | None = None
    warning_threshold: int | None = None
    danger_threshold: int | None = None


def _primitives_from_map(
    color_map: dict[str, str], *, dark: bool = False
) -> ThemePrimitives:
    """Build a ThemePrimitives by reading each token name from color_map.

    The canonical mapping is 1:1 — the color row's ``type`` field is the
    primitive's field name (optionally with ``dark_`` prefix for dark
    mode). Anything not in the map stays empty ('').
    """
    prefix = "dark_" if dark else ""
    return ThemePrimitives(
        **{
            field_name: color_map.get(f"{prefix}{field_name}", "")
            for field_name in ThemePrimitives.model_fields
        }
    )


async def resolve_settings_theme(
    pool: asyncpg.Pool,
    redis: Redis,
    settings_id: UUID,
    bypass_cache: bool = False,
) -> SettingsThemeResult | None:
    """Resolve theme primitives + thresholds for a settings_resource id.

    ``settings_id`` is the resource id (the canonical pointer carried on
    ``ProfileIdentityContext.settings_id``). The first step translates to
    the owning ``setting_artifact`` id via the ``search_settings``
    black-box, which walks ``setting_settings_junction`` for us — no
    inline SQL in this module.
    """
    # Step 1a: resource id → artifact id via the canonical search black-box
    async with pool.acquire() as conn:
        artifact_ids, _ = await search_settings(
            conn,
            setting_ids=[settings_id],
            limit_count=1,
        )
    if not artifact_ids:
        return None
    artifact_id = artifact_ids[0]

    # Step 1b: Get setting artifact with junction IDs
    async with pool.acquire() as conn:
        artifacts = await get_setting_artifacts(
            conn,
            [artifact_id],
            colors=True,
            thresholds=True,
            flags=True,
        )
    if not artifacts:
        return None

    artifact = artifacts[0]
    color_ids = artifact.color_ids or []
    threshold_ids = artifact.threshold_ids or []
    flag_ids = artifact.flag_ids or []

    # Step 2: Fetch resources in parallel
    async def _get_colors():
        async with pool.acquire() as c:
            return await get_colors(c, color_ids, redis, bypass_cache)

    async def _get_thresholds():
        async with pool.acquire() as c:
            return await get_thresholds(c, threshold_ids, redis, bypass_cache)

    async def _get_flags():
        async with pool.acquire() as c:
            return await get_flags(c, flag_ids, redis, bypass_cache)

    colors_res, thresholds_res, flags_res = await asyncio.gather(
        _get_colors() if color_ids else _empty(),
        _get_thresholds() if threshold_ids else _empty(),
        _get_flags() if flag_ids else _empty(),
    )

    # Step 3: Check active flag
    is_active = any(f.name == "setting_active" and f.value is True for f in flags_res)
    if not is_active:
        return SettingsThemeResult(is_active=False)

    # Step 4: Map colors by type → field-name
    color_map: dict[str, str] = {c.type: c.hex_code for c in colors_res}
    threshold_map: dict[str, int] = {t.type: t.value for t in thresholds_res}

    return SettingsThemeResult(
        is_active=True,
        light=_primitives_from_map(color_map, dark=False),
        dark=_primitives_from_map(color_map, dark=True),
        success_threshold=threshold_map.get("success"),
        warning_threshold=threshold_map.get("warning"),
        danger_threshold=threshold_map.get("danger"),
    )


async def resolve_thresholds(
    pool: asyncpg.Pool,
    redis: Redis,
    profile_id: UUID | None,
    bypass_cache: bool = False,
) -> dict[str, int | float]:
    """Resolve threshold values for a profile.

    Resolves profile → identity → settings_id → thresholds.
    Returns defaults if profile or settings not found.
    """
    from app.infra.profile_identity_context import resolve_profile_identity_context

    success, warning, danger = 85, 80, 70

    if not profile_id:
        return {"success": success, "warning": warning, "danger": danger}

    identity = await resolve_profile_identity_context(
        pool, profile_id, redis, bypass_cache=bypass_cache
    )
    if not identity or not identity.settings_id:
        return {"success": success, "warning": warning, "danger": danger}

    theme = await resolve_settings_theme(
        pool, redis, identity.settings_id, bypass_cache=bypass_cache
    )
    if theme:
        success = theme.success_threshold or success
        warning = theme.warning_threshold or warning
        danger = theme.danger_threshold or danger

    return {"success": success, "warning": warning, "danger": danger}


async def _empty() -> list:
    return []


async def resolve_platform_default_settings_resource_id(
    pool: asyncpg.Pool,
) -> UUID | None:
    """Find the active platform-default setting (no department_ids) and
    return its setting *resource* id.

    Used by ``profile_identity_context`` when a profile has no primary
    department to fall back on. Without this, ``settings_id`` would be
    ``None`` and theme resolution would silently return the shadcn
    defaults instead of the seeded LearnLoop palette.

    Mirrors the realm-level lookup in
    ``keycloak_resolvers.resolve_auths_for_realm``: search all active
    setting artifacts, filter Python-side for empty ``department_ids``,
    take the first match's ``setting_ids[0]`` (the resource id via the
    ``setting_settings_junction`` black-box).
    """
    async with pool.acquire() as conn:
        artifact_ids, _ = await search_settings(
            conn, active_only=True, limit_count=100000,
        )
        if not artifact_ids:
            return None
        artifacts = await get_setting_artifacts(
            conn, artifact_ids, settings=True,
        )
    for sa in artifacts:
        if not sa.department_ids and sa.setting_ids:
            return sa.setting_ids[0]
    return None
