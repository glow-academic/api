"""Document file upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.document.file_upload.

Soft/accept (canonical lifecycle): a propose call uploads the file with
``soft=true`` (staged dormant); the ack call posts ``{idempotency_key, accept}``
with NO file (``file`` is optional) to promote/reject. ``accept`` is placed in
the audit ``arguments`` on the ack so the replay gate's ``_is_bare_ack`` skips it
rather than replaying the propose receipt.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.infra.document.file_upload import file_upload_document_impl
from app.infra.document.group import group_document_impl
from app.infra.document.types import FileUploadDocumentApiResponse
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()


@router.post("/file_upload", response_model=FileUploadDocumentApiResponse)
async def upload_file(
    http_request: Request,
    response: Response,
    file: UploadFile | None = File(None),
    idempotency_key: UUID | None = Form(None),
    soft: bool = Form(False),
    accept: bool | None = Form(None),
) -> FileUploadDocumentApiResponse:
    """Upload a file for later use in documents (soft/accept dormant flow)."""
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
            # Ack call: no file. Carry `accept` in arguments so the replay gate's
            # _is_bare_ack skips it (don't replay the propose receipt).
            file_bytes = None
            filename = None
            content_type = None
            arguments: dict = {"accept": accept}
        else:
            if file is None or not file.filename:
                raise HTTPException(status_code=400, detail="Missing file")
            file_bytes = await file.read()
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Empty file")
            filename = file.filename
            content_type = file.content_type or get_content_type(file.filename)
            arguments = {
                "filename": filename,
                "content_type": content_type,
                "size": len(file_bytes),
            }

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

        async def _runner() -> FileUploadDocumentApiResponse:
            return await file_upload_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                soft=soft,
                accept=accept,
                idempotency_key=idempotency_key,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="file_upload",
            arguments=arguments,
            response_model=FileUploadDocumentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=idempotency_key,  # idempotency replay gate
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
