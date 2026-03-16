"""Agent docs endpoint — composable infra architecture."""

from fastapi import APIRouter, Request, Response

from app.infra.agent.docs import docs_agent_impl
from app.infra.docs.types import ComposedDocsResponse
from app.infra.docs_helper import DocsApiRequest
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder

router = APIRouter()


@router.post("/docs", response_model=ComposedDocsResponse)
async def get_agent_docs_endpoint(
    body: DocsApiRequest,
    http_request: Request,
    response: Response,
) -> ComposedDocsResponse:
    """Get composed documentation for the agent artifact."""
    profile_id = http_request.state.profile_id
    pool = get_pool()
    redis = get_redis_client()

    async def _runner() -> ComposedDocsResponse:
        return await docs_agent_impl(
            pool,
            redis,
            profile_id=profile_id,
            entity_id=body.entity_id,
        )

    return await run_artifact_operation_with_audit(
        pool,
        redis,
        artifact="agent",
        profile_id=profile_id,
        session_id=http_request.state.session_id,
        operation="docs",
        arguments=body.model_dump(mode="json"),
        response_model=ComposedDocsResponse,
        runner=_runner,
        upload_folder=get_upload_folder(),
    )
