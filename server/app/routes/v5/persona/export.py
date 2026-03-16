"""Persona export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.globals import get_pool, get_redis_client
from app.infra.persona.export import export_persona_impl
from app.infra.persona.types import (
    ExportPersonaApiRequest,
    ExportPersonaApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportPersonaApiResponse)
async def export_personas(
    body: ExportPersonaApiRequest,
    http_request: Request,
) -> ExportPersonaApiResponse:
    """Export all personas as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_persona_impl(
        pool,
        redis,
        profile_id=profile_id,
        persona_id=body.persona_id,
    )
