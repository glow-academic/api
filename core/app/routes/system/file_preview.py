"""Group file preview endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.group.file_preview.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.group.file_preview import file_preview_group_impl
from app.infra.group.media_types import (
    FilePreviewGroupApiRequest,
    FilePreviewGroupApiResult,
)
from app.infra.system.group import group_system_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/file_preview", response_model=None)
async def preview_file(
    request: FilePreviewGroupApiRequest,
    http_request: Request,
    response: Response,
) -> Response:
    """Return a PNG preview of the first page of a PDF upload."""
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
            group_result = await group_system_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> FilePreviewGroupApiResult:
            return await file_preview_group_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_id=request.file_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="system",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="file_preview",
            arguments={"file_id": str(request.file_id)},
            response_model=FilePreviewGroupApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        return Response(
            content=result.preview_bytes,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600, must-revalidate"},
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="file_preview_group",
            request=http_request,
        )
