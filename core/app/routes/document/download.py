"""Document download — single endpoint for all modalities."""

import os
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.tools.entries.uploads.get import get_upload
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type
from app.utils.storage.range_response import create_range_response

router = APIRouter()


@router.get("/download/{upload_id}", response_model=None)
async def download(upload_id: str, http_request: Request) -> Response:
    """Download any file by upload ID with range support."""
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
        filename = os.path.basename(result.file_path or "")
        encoded = urllib.parse.quote(filename, safe="")
        disposition = f"inline; filename=\"{encoded}\"; filename*=UTF-8''{encoded}"

        return create_range_response(
            file_path=file_path,
            content_type=content_type,
            content_disposition=disposition,
            range_header=http_request.headers.get("range"),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="download_document",
            request=http_request,
        )
        raise
