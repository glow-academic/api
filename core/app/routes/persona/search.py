"""Persona search endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.persona.search.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.persona.audit import run_persona_operation_with_audit
from app.infra.persona.search import search_persona_impl
from app.infra.persona.types import ListPersonaApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


class SearchPersonaApiRequest(BaseModel):
    """Request model for persona search endpoint."""

    # Main filters
    search: str | None = Field(None, description="Full-text search query for personas")
    scenario_ids: list[UUID] | None = Field(None, description="Filter by scenario UUIDs")
    field_ids: list[UUID] | None = Field(None, description="Filter by field UUIDs")
    filter_department_ids: list[UUID] | None = Field(None, description="Filter by department UUIDs")
    # Facet search text
    scenario_search: str | None = Field(None, description="Search text for scenario facet")
    field_search: str | None = Field(None, description="Search text for field facet")
    department_search: str | None = Field(None, description="Search text for department facet")
    color_search: str | None = Field(None, description="Search text for color facet")
    icon_search: str | None = Field(None, description="Search text for icon facet")
    voice_search: str | None = Field(None, description="Search text for voice facet")
    instruction_search: str | None = Field(None, description="Search text for instruction facet")
    # Pagination
    page_size: int | None = Field(12, description="Number of results per page")
    page_offset: int | None = Field(0, description="Pagination offset")


@router.post("/search", response_model=ListPersonaApiResponse)
async def search_persona(
    request: SearchPersonaApiRequest,
    http_request: Request,
    response: Response,
) -> ListPersonaApiResponse:
    """Search personas — composable infra architecture."""
    tags = ["personas"]

    try:
        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        async def _runner() -> ListPersonaApiResponse:
            return await search_persona_impl(
                pool,
                redis,
                profile_id=profile_id,
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
                page_size=request.page_size or 12,
                page_offset=request.page_offset or 0,
            )

        result = await run_persona_operation_with_audit(
            pool,
            redis,
            profile_id=profile_id,
            session_id=http_request.state.session_id,
            operation="search",
            arguments=request.model_dump(mode="json"),
            response_model=ListPersonaApiResponse,
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
            operation="search_persona",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
