"""Persona delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.persona.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.persona.delete import delete_persona_impl
from app.infra.persona.group import group_persona_impl
from app.infra.persona.types import (
    DeletePersonaApiRequest,
    DeletePersonaApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeletePersonaApiResponse)
async def delete_persona(
    request: DeletePersonaApiRequest,
    http_request: Request,
    response: Response,
) -> DeletePersonaApiResponse:
    """Bulk delete personas — composable infra architecture."""
    tags = ["personas"]

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

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_persona_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> DeletePersonaApiResponse:
            return await delete_persona_impl(
                pool,
                redis,
                profile_id=profile_id,
                ids=request.ids,
                session_id=session_id,
                idempotency_key=request.idempotency_key,
                accept=request.accept if request.idempotency_key else None,
                # All-matching path
                all=request.all,
                excluded_ids=request.excluded_ids,
                search=request.search,
                scenario_ids=request.scenario_ids,
                field_ids=request.field_ids,
                filter_department_ids=request.filter_department_ids,
                scenario_search=request.scenario_search,
                field_search=request.field_search,
                department_search=request.department_search,
                color_search=request.color_search,
                icon_search=request.icon_search,
                voice_search=request.voice_search,
                instruction_search=request.instruction_search,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="persona",
            profile_id=profile_id,
            session_id=session_id,
            operation="delete",
            group_id=group_id,
            arguments=request.model_dump(mode="json"),
            response_model=DeletePersonaApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_persona",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
