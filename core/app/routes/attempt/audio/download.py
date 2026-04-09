"""Attempt audio download."""

import os
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.globals import AUDIO_FOLDER, get_pool
from app.tools.entries.uploads.get import get_upload
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type
from app.utils.storage.range_response import create_range_response

router = APIRouter()


class AudioDownloadRequest(BaseModel):
    upload_id: uuid.UUID


@router.post("/download", response_model=None)
async def download_audio(
    request: AudioDownloadRequest,
    http_request: Request,
) -> Response:
    """Download an audio file by upload ID."""
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            result = await get_upload(conn, request.upload_id)

        if result is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        stored_path = result.file_path or ""
        file_path = os.path.join(AUDIO_FOLDER, os.path.basename(stored_path))

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Audio file not found")

        content_type = get_content_type(result.file_path or "", result.mime_type or "")

        filename = os.path.basename(result.file_path or "")
        encoded_filename = urllib.parse.quote(filename, safe="")
        content_disposition = f"inline; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"

        return create_range_response(
            file_path=file_path,
            content_type=content_type,
            content_disposition=content_disposition,
            range_header=http_request.headers.get("range"),
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="download_attempt_audio",
            request=http_request,
        )
        raise
