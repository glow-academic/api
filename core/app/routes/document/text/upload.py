"""Document text upload."""

import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from app.infra.globals import UPLOAD_FOLDER, get_pool, get_redis_client
from app.tools.entries.uploads.create import create_upload
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

ALLOWED_TEXT_TYPES = {
    "text/plain",
    "text/html",
    "text/csv",
    "text/markdown",
    "text/xml",
    "application/json",
    "application/xml",
}


class TextUploadResponse(BaseModel):
    upload_id: uuid.UUID


@router.post("/upload", response_model=TextUploadResponse)
async def upload_text(
    file: UploadFile,
    http_request: Request,
    response: Response,
) -> TextUploadResponse:
    """Upload a text file via multipart form-data."""
    tags = ["uploads"]

    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        content_type = file.content_type or get_content_type(file.filename)
        if content_type not in ALLOWED_TEXT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported text type: {content_type}",
            )

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        upload_uuid = uuid.uuid4()
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = ".txt"

        final_file_path = f"{upload_uuid}{ext}"
        final_full_path = UPLOAD_FOLDER / f"{upload_uuid}{ext}"

        with open(final_full_path, "wb") as f:
            f.write(file_bytes)

        session_id = getattr(http_request.state, "session_id", None)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await create_upload(
                conn,
                session_id=uuid.UUID(session_id) if session_id else uuid.UUID(int=0),
                file_path=final_file_path,
                mime_type=content_type,
                size=len(file_bytes),
            )

        await invalidate_tags(tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return TextUploadResponse(upload_id=result.id)

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="upload_document_text",
            request=http_request,
        )
        raise
