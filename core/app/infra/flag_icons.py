"""Flag icon hydration.

`get_flags` / `search_flags` return flags with `icon_id` but no SVG — keeping
those tools pure data-access. Artifact contexts that need to render flag icons
call `hydrate_flag_icons` below to fill in the `icon` field on each flag with
the SVG markup pulled from icons_resource. Sections/UI then reads `flag.icon`.
"""

from __future__ import annotations

from typing import Any

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.resources.icons.get import get_icons


async def hydrate_flag_icons(
    flags: list[Any],
    conn: asyncpg.Connection,
    redis: Redis,
    bypass_cache: bool = False,
) -> None:
    """Resolve `icon_id` → `icon` (SVG markup) in place on each flag.

    Flags without an icon_id (or with an id that doesn't exist in
    icons_resource) are left with `icon=None`.
    """
    icon_ids = list({f.icon_id for f in flags if getattr(f, "icon_id", None)})
    if not icon_ids:
        return
    icons = await get_icons(conn, icon_ids, redis, bypass_cache=bypass_cache)
    icon_by_id = {i.id: getattr(i, "value", None) for i in icons}
    for f in flags:
        if getattr(f, "icon_id", None):
            f.icon = icon_by_id.get(f.icon_id)
