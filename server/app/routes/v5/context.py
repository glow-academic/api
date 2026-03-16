"""POST /context — identity + permissions + theme.

Thin wrapper over resolve_profile_identity_context().
Root-level layout route (mounted at /v5/context).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.identity.settings import resolve_settings_theme
from app.infra.identity.simulatable import SIMULATABLE_ROLES
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.shared_types import (
    GetProfileContextApiRequest,
    QGetProfileContextV4RoleResource,
)
from app.infra.profile.types import (
    ProfileContextApiResponse,
    ThemePrimitives,
)
from app.tools.resources.roles.get import get_roles
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/context", response_model=ProfileContextApiResponse)
async def get_profile_context(
    request: GetProfileContextApiRequest,
    http_request: Request,
    response: Response,
) -> ProfileContextApiResponse:
    """Identity + permissions + theme context endpoint."""
    try:
        try:
            profile_id = http_request.state.profile_id
        except AttributeError:
            profile_id = None

        if not profile_id:
            raise HTTPException(status_code=404, detail="Profile ID is required")

        bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"
        pool = get_pool()
        redis = get_redis_client()
        session_id = getattr(http_request.state, "session_id", None)

        async def _runner() -> ProfileContextApiResponse:
            identity = await resolve_profile_identity_context(
                pool, profile_id, redis, bypass_cache=bypass_cache
            )
            if not identity:
                raise HTTPException(status_code=404, detail="Profile not found")

            scoped_roles = sorted(SIMULATABLE_ROLES.get(identity.role, set()))

            async def _fetch_roles() -> list:
                async with pool.acquire() as c:
                    return await get_roles(c, None, redis, bypass_cache=bypass_cache)

            async def _fetch_theme() -> ThemePrimitives | None:
                if not identity.settings_id:
                    return None
                theme = await resolve_settings_theme(
                    pool, redis, identity.settings_id, bypass_cache=bypass_cache
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
                    role=r.role,
                    name=r.name,
                    description=r.description,
                    icon_value=None,
                    color_hex=None,
                )
                for r in roles_raw
            ]

            req_identity = getattr(http_request.state, "identity", None)
            is_emulation = (
                getattr(req_identity, "is_emulation", False) if req_identity else False
            )
            emulation_depth = (
                getattr(req_identity, "emulation_depth", 0) if req_identity else 0
            )

            return ProfileContextApiResponse(
                id=profile_id,
                name=identity.name,
                role=identity.role,
                active=identity.is_active,
                role_artifacts=identity.role_artifacts,
                scoped_roles=scoped_roles,
                department_ids=[str(d) for d in identity.department_ids],
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

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="profile",
            profile_id=profile_id,
            session_id=session_id,
            operation="context",
            arguments={"profile_id": str(profile_id)},
            bypass_cache=bypass_cache,
            response_model=ProfileContextApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_profile_context",
            request=http_request,
        )
