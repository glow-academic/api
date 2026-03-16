"""Scenario file download — streaming with range support and PDF preview."""

import os
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse

from app.infra.globals import UPLOAD_FOLDER, get_pool
from app.tools.entries.uploads.get import get_upload
from app.utils.document.pdf_first_page_to_image_bytes import (
    pdf_first_page_to_image_bytes,
)
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter(prefix="/file", tags=["file"])


def _create_range_streaming_response(
    file_path: str,
    content_type: str,
    range_header: str | None,
    content_disposition: str,
) -> Response:
    """Create a streaming response with HTTP Range support."""
    file_size = os.path.getsize(file_path)
    start = 0
    end = file_size - 1

    if range_header:
        range_spec = range_header.replace("bytes=", "")
        if "-" in range_spec:
            parts = range_spec.split("-")
            if parts[0]:
                start = int(parts[0])
            if parts[1]:
                end = int(parts[1])

    if start >= file_size:
        start = 0
    if end >= file_size:
        end = file_size - 1

    content_length = end - start + 1
    chunk_size = 1024 * 1024

    def iter_file():
        with open(file_path, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                read_size = min(chunk_size, remaining)
                data = f.read(read_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    headers = {
        "Content-Disposition": content_disposition,
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Cache-Control": "private, max-age=0, must-revalidate",
    }

    status_code = 206 if range_header else 200
    return StreamingResponse(
        iter_file(),
        status_code=status_code,
        media_type=content_type,
        headers=headers,
    )


@router.get("/{upload_id}/download", response_model=None)
async def download_file(
    upload_id: str,
    http_request: Request,
) -> FileResponse | Response:
    """Download a document file by upload ID."""
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
        encoded_filename = urllib.parse.quote(filename, safe="")
        content_disposition = f"inline; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"

        if content_type.startswith("video/"):
            range_header = http_request.headers.get("range")
            return _create_range_streaming_response(
                file_path=file_path,
                content_type=content_type,
                range_header=range_header,
                content_disposition=content_disposition,
            )

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
            operation="download_scenario_file",
            request=http_request,
        )
        raise


@router.get("/{upload_id}/preview", response_model=None)
async def preview_file(
    upload_id: str,
    http_request: Request,
) -> Response:
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
            headers={
                "Cache-Control": "private, max-age=3600, must-revalidate",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="preview_scenario_file",
            request=http_request,
        )
        raise
