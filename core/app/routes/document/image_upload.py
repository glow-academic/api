"""Document image upload endpoint — composable infra architecture.

Mirror of ``app.routes.scenario.image_upload``. Core logic lives in
``app.infra.document.image_upload``; this is just the HTTP binding +
audit wrapper.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.infra.document.group import group_document_impl
from app.infra.document.image_upload import image_upload_document_impl
from app.infra.document.types import ImageUploadDocumentApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


@router.post("/image_upload", response_model=ImageUploadDocumentApiResponse)
async def upload_image(
    http_request: Request,
    response: Response,
    file: UploadFile | None = File(None),
    name: str | None = None,
    description: str | None = None,
    idempotency_key: UUID | None = Form(None),
    soft: bool = Form(False),
    accept: bool | None = Form(None),
) -> ImageUploadDocumentApiResponse:
    """Upload an image for later use in documents (soft/accept dormant flow)."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        is_ack = accept is not None and idempotency_key is not None

        if is_ack:
            file_bytes = None
            filename = None
            content_type = None
            arguments: dict = {"accept": accept}
        else:
            if file is None or not file.filename:
                raise HTTPException(status_code=400, detail="Missing filename")

            content_type = file.content_type or get_content_type(file.filename)
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image type: {content_type}",
                )

            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Empty file")
            filename = file.filename
            arguments = {
                "filename": filename,
                "content_type": content_type,
                "size": len(file_bytes),
                "name": name,
                "description": description,
            }

        pool = get_pool()
        redis = get_redis_client()

        group_id = None
        if session_id:
            group_result = await group_document_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner(call_id: UUID | None = None) -> ImageUploadDocumentApiResponse:
            return await image_upload_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                name=name,
                description=description,
                soft=soft,
                accept=accept,
                idempotency_key=idempotency_key,
                call_id=call_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            operation="image_upload",
            arguments=arguments,
            response_model=ImageUploadDocumentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=idempotency_key,
            group_id=group_id,
        )

        response.headers["X-Invalidate-Tags"] = "uploads,resources,images"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="image_upload_document",
            request=http_request,
        )
