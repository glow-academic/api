"""Persona GET endpoint — thin HTTP adapter over the canonical shared operation."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.persona.audit import run_persona_operation_with_audit
from app.infra.persona.get import get_persona_impl
from app.infra.persona.types import (
    GetPersonaApiRequest,
    GetPersonaApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/get", response_model=GetPersonaApiResponse)
async def get_persona(
    request: GetPersonaApiRequest,
    http_request: Request,
    response: Response,
) -> GetPersonaApiResponse:
    """Get persona information using the canonical shared persona operation."""
    bypass_cache = http_request.headers.get("X-Bypass-Cache") == "1"

    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()
        request_payload = request.model_dump(mode="json")

        async def _runner() -> GetPersonaApiResponse:
            return await get_persona_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                persona_id=request.persona_id,
                draft_id=request.draft_id,
                parameter_ids=[UUID(pid) for pid in request.parameter_ids]
                if request.parameter_ids
                else None,
                color_search=request.color_search,
                icon_search=request.icon_search,
                descriptions_search=request.descriptions_search,
                instructions_search=request.instructions_search,
                color_show_selected=request.color_show_selected,
                icon_show_selected=request.icon_show_selected,
                bypass_cache=bypass_cache,
            )

        response_data = await run_persona_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation="get",
            arguments=request_payload,
            bypass_cache=bypass_cache,
            response_model=GetPersonaApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Cache-Tags"] = "personas"
        response.headers["X-Cache-Hit"] = "0"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="get_persona",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
