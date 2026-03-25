"""Output: context — resolve profile identity + permissions + theme."""

import asyncio
from typing import Any
from uuid import UUID

from app.infra.globals import UPLOAD_FOLDER, get_internal_sio, get_pool, get_redis_client, sio
from app.infra.identity.settings import resolve_settings_theme
from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.tools.entries.append_call_event import append_call_event
from app.tools.resources.roles.get import get_roles
from app.utils.logging.db_logger import get_logger

logger = get_logger(__name__)

internal_sio = get_internal_sio()


@internal_sio.on("context")  # type: ignore
async def context_output(data: dict[str, Any]) -> None:
    sid = data.get("sid", "")
    call_id = data.get("call_id")
    if call_id:
        append_call_event(UUID(call_id), "context", data, UPLOAD_FOLDER)

    profile_id_str = data.get("profile_id")
    if not profile_id_str:
        await sio.emit("context_error", {"message": "Missing profile_id"}, room=sid)
        return

    try:
        profile_id = UUID(profile_id_str)
        bypass_cache = data.get("bypass_cache", False)
        pool = get_pool()
        redis = get_redis_client()

        identity = await resolve_profile_identity_context(
            pool, profile_id, redis, bypass_cache=bypass_cache
        )
        if not identity:
            await sio.emit(
                "context_error", {"message": "Profile not found"}, room=sid
            )
            return

        scoped_roles = sorted(SIMULATABLE_ROLES.get(identity.role, set()))

        async def _fetch_roles() -> list:
            async with pool.acquire() as c:
                return await get_roles(c, None, redis, bypass_cache=bypass_cache)

        async def _fetch_theme() -> dict[str, Any] | None:
            if not identity.settings_id:
                return None
            theme = await resolve_settings_theme(
                pool, redis, identity.settings_id, bypass_cache=bypass_cache
            )
            if not theme or not theme.is_active or not theme.primary_color:
                return None
            return {
                "primary": theme.primary_color,
                "accent": theme.accent,
                "background": theme.background,
                "surface": theme.surface,
                "success": theme.success,
                "warning": theme.warning,
                "error": theme.error,
                "chart1": theme.chart1,
                "chart2": theme.chart2,
                "chart3": theme.chart3,
                "chart4": theme.chart4,
                "chart5": theme.chart5,
            }

        roles_raw, theme = await asyncio.gather(_fetch_roles(), _fetch_theme())

        role_resources = [
            {
                "role": r.role,
                "name": r.name,
                "description": r.description,
                "icon_value": None,
                "color_hex": None,
            }
            for r in roles_raw
        ]

        result = {
            "id": profile_id_str,
            "name": identity.name,
            "role": identity.role,
            "active": identity.is_active,
            "role_artifacts": identity.role_artifacts,
            "scoped_roles": scoped_roles,
            "department_ids": [str(d) for d in identity.department_ids],
            "primary_department_id": str(identity.primary_department_id)
            if identity.primary_department_id
            else None,
            "settings_id": str(identity.settings_id) if identity.settings_id else None,
            "theme": theme,
            "session_id": identity.session_id,
            "role_resources": role_resources,
        }

        await sio.emit("context_result", result, room=sid)

    except Exception as e:
        logger.exception(f"Error in context output: {e}")
        await sio.emit(
            "context_error", {"message": f"Failed to resolve context: {e}"}, room=sid
        )
