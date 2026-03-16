"""Scenario preview — PDF first-page thumbnail."""

import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.tools.entries.uploads.get import get_upload
from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()


@router.get("/preview/{upload_id}", response_model=None)
async def preview(upload_id: str, http_request: Request) -> Response:
    """Return a PNG preview of the first page of a PDF upload."""
    try:
        upload_id_uuid = uuid.UUID(upload_id)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await get_upload(conn, upload_id_uuid)

        if result is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        stored_path = result.file_path or ""
        file_path = os.path.join(UPLOAD_FOLDER, stored_path)

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        content_type = get_content_type(result.file_path or "", result.mime_type or "")
        if content_type != "application/pdf":
            raise HTTPException(
                status_code=400, detail="Preview only supported for PDF files"
            )

        preview_bytes = pdf_first_page_to_image_bytes(file_path)
        if not preview_bytes:
            raise HTTPException(status_code=500, detail="Failed to generate preview")

        return Response(
            content=preview_bytes,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600, must-revalidate"},
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="preview_scenario",
            request=http_request,
        )
        raise
