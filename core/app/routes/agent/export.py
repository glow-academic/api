"""Agent export endpoint — composable infra architecture."""

from fastapi import APIRouter, Request

from app.infra.agent.export import export_agent_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.agent.types import (
    ExportAgentApiRequest,
    ExportAgentApiResponse,
)

router = APIRouter()


@router.post("/export", response_model=ExportAgentApiResponse)
async def export_agents(
    body: ExportAgentApiRequest,
    http_request: Request,
) -> ExportAgentApiResponse:
    """Export all agents as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    return await export_agent_impl(
        pool,
        redis,
        profile_id=profile_id,
        agent_id=body.agent_id,
    )
