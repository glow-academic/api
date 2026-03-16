"""Persona create endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.persona.create.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.persona.audit import run_persona_operation_with_audit
from app.infra.persona.create import create_persona_impl
from app.infra.persona.types import (
    CreatePersonaApiRequest,
    CreatePersonaApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/create", response_model=CreatePersonaApiResponse)
async def create_persona(
    request: CreatePersonaApiRequest,
    http_request: Request,
    response: Response,
) -> CreatePersonaApiResponse:
    """Create personas using composable infra architecture."""
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

        async def _runner() -> CreatePersonaApiResponse:
            return await create_persona_impl(
                pool,
                redis,
                profile_id=profile_id,
                items=request.personas,
                session_id=session_id,
            )

        response_data = await run_persona_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=session_id,
            operation="create",
            arguments={
                "personas": [item.model_dump(mode="json") for item in request.personas]
            },
            response_model=CreatePersonaApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "personas"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="create_persona",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
