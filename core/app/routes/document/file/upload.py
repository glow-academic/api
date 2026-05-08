"""Document file upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.document.file_upload.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile

from app.infra.document.file_upload import file_upload_document_impl
from app.infra.document.group import group_document_impl
from app.infra.document.types import FileUploadDocumentApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()


@router.post("/upload", response_model=FileUploadDocumentApiResponse)
async def upload_file(
    file: UploadFile,
    http_request: Request,
    response: Response,
) -> FileUploadDocumentApiResponse:
    """Upload a file for later use in documents."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        # -- Validate file ------------------------------------------------------
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        content_type = file.content_type or get_content_type(file.filename)

        # -- Run with audit -----------------------------------------------------
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_document_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
            )
            group_id = group_result.group_id

        async def _runner() -> FileUploadDocumentApiResponse:
            return await file_upload_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=file.filename,
                content_type=content_type,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="file_upload",
            arguments={
                "filename": file.filename,
                "content_type": content_type,
                "size": len(file_bytes),
            },
            response_model=FileUploadDocumentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = "uploads,resources,files"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="file_upload_document",
            request=http_request,
        )
