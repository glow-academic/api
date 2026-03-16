"""Resolve settings theme — composes canonical black boxes.

Given a settings_id (artifact), fetches:
  1. Setting artifact with colors, thresholds, flags junctions
  2. Colors, thresholds, flags resources in parallel
  3. Maps by type in Python → theme primitives + thresholds

No inline SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.setting.get import (
    get_settings as get_setting_artifacts,
)
from app.tools.resources.colors.get import get_colors
from app.tools.resources.flags.get import get_flags
from app.tools.resources.thresholds.get import get_thresholds


@dataclass(frozen=True)
class SettingsThemeResult:
    """Resolved theme data from a setting artifact."""

    is_active: bool
    primary_color: str | None = None
    accent: str | None = None
    background: str | None = None
    surface: str | None = None
    success: str | None = None
    warning: str | None = None
    error: str | None = None
    chart1: str | None = None
    chart2: str | None = None
    chart3: str | None = None
    chart4: str | None = None
    chart5: str | None = None
    success_threshold: int | None = None
    warning_threshold: int | None = None
    danger_threshold: int | None = None


async def resolve_settings_theme(
    pool: asyncpg.Pool,
    redis: Redis,
    settings_id: UUID,
    bypass_cache: bool = False,
) -> SettingsThemeResult | None:
    """Resolve theme primitives + thresholds from a setting artifact.

    Composes canonical black boxes — no inline SQL.
    """
    # Step 1: Get setting artifact with junction IDs
    async with pool.acquire() as conn:
        artifacts = await get_setting_artifacts(
            conn,
            [settings_id],
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

    # Step 4: Map colors by type
    color_map: dict[str, str] = {}
    for c in colors_res:
        color_map[c.type] = c.hex_code

    # Step 5: Map thresholds by type
    threshold_map: dict[str, int] = {}
    for t in thresholds_res:
        threshold_map[t.type] = t.value

    return SettingsThemeResult(
        is_active=True,
        primary_color=color_map.get("primary"),
        accent=color_map.get("accent"),
        background=color_map.get("background"),
        surface=color_map.get("surface"),
        success=color_map.get("success"),
        warning=color_map.get("warning"),
        error=color_map.get("error"),
        chart1=color_map.get("chart1"),
        chart2=color_map.get("chart2"),
        chart3=color_map.get("chart3"),
        chart4=color_map.get("chart4"),
        chart5=color_map.get("chart5"),
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
