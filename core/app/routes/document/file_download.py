"""Document file download endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.document.file_download.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.document.file_download import file_download_document_impl
from app.infra.document.group import group_document_impl
from app.infra.document.types import (
    FileDownloadDocumentApiRequest,
    FileDownloadDocumentApiResult,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.storage.range_response import create_range_response

router = APIRouter()


@router.post("/file_download", response_model=None)
async def download_file(
    request: FileDownloadDocumentApiRequest,
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
            group_result = await group_document_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> FileDownloadDocumentApiResult:
            return await file_download_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_id=request.file_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="file_download",
            arguments={"file_id": str(request.file_id)},
            response_model=FileDownloadDocumentApiResult,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        import urllib.parse
        encoded = urllib.parse.quote(result.filename, safe="")
        # User-uploaded content: force a download (attachment) so a malicious
        # .html/SVG with a client-chosen text/html mime can never be rendered
        # inline in the app origin (stored XSS on download). The client never
        # relies on inline disposition — its viewers fetch the bytes and
        # render from a blob URL, so attachment does not break preview.
        content_disposition = (
            f"attachment; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"
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
            operation="file_download_document",
            request=http_request,
        )
