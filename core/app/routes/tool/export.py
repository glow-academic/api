"""Tool export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.tool.export import export_tool_impl
from app.infra.tool.group import group_tool_impl
from app.infra.tool.types import ExportToolApiRequest, ExportToolApiResponse
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/export", response_model=ExportToolApiResponse)
async def export_tools(
    body: ExportToolApiRequest,
    http_request: Request,
) -> ExportToolApiResponse:
    """Export all tools as a clean, denormalized CSV."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_tool_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = body.accept is not None and body.idempotency_key is not None

        async def _runner(call_id: UUID | None = None) -> ExportToolApiResponse:
            return await export_tool_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                tool_id=body.tool_id,
                soft=body.soft,
                accept=body.accept,
                idempotency_key=body.idempotency_key,
                call_id=call_id,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="export",
            arguments={"accept": body.accept} if is_ack else body.model_dump(mode="json"),
            response_model=ExportToolApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=body.idempotency_key,  # idempotency replay gate
        )
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="export_tool",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
