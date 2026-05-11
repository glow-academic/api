"""Eval file download endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.eval.file_download.
"""

from __future__ import annotations

import urllib.parse

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.eval.file_download import file_download_eval_impl
from app.infra.eval.group import group_eval_impl
from app.infra.eval.types import (
    FileDownloadEvalApiRequest,
    FileDownloadEvalApiResult,
)
from app.utils.error.handle_route_error import handle_route_error
from app.utils.storage.range_response import create_range_response

router = APIRouter()


@router.post("/download", response_model=None)
async def download_file(
    request: FileDownloadEvalApiRequest,
    http_request: Request,
    response: Response,
) -> Response:
    """Download a file by file resource ID."""
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
            group_result = await group_eval_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> FileDownloadEvalApiResult:
            return await file_download_eval_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_id=request.file_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="eval",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="file_download",
            arguments={"file_id": str(request.file_id)},
            response_model=FileDownloadEvalApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        encoded = urllib.parse.quote(result.filename, safe="")
        content_disposition = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8\'\'{encoded}"
        )

        return create_range_response(
            file_path=result.file_path,
            content_type=result.content_type,
            content_disposition=content_disposition,
            range_header=http_request.headers.get("range"),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="file_download_eval",
            request=http_request,
        )
