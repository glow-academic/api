"""Scenario text download."""

import os
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.tools.entries.uploads.get import get_upload
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter(prefix="/text", tags=["text"])


@router.get("/{upload_id}/download", response_model=None)
async def download_text(
    upload_id: str,
    http_request: Request,
) -> FileResponse:
    """Download a text file by upload ID."""
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
            raise HTTPException(status_code=404, detail="Text file not found")

        content_type = get_content_type(result.file_path or "", result.mime_type or "")

        filename = os.path.basename(result.file_path or "")
        encoded_filename = urllib.parse.quote(filename, safe="")
        content_disposition = f"inline; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"

        return FileResponse(
            path=file_path,
            media_type=content_type,
            headers={
                "Content-Disposition": content_disposition,
                "Cache-Control": "private, max-age=0, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="download_scenario_text",
            request=http_request,
        )
        raise
