"""Scenario image uploads — upload and download for image files."""

import os
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.infra.globals import IMAGE_FOLDER, get_pool, get_redis_client
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter(prefix="/image", tags=["image"])

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


class ImageUploadResponse(BaseModel):
    upload_id: uuid.UUID


@router.post("/upload", response_model=ImageUploadResponse)
async def upload_image(
    file: UploadFile,
    http_request: Request,
    response: Response,
) -> ImageUploadResponse:
    """Upload an image file via multipart form-data."""
    tags = ["uploads"]

    try:
        if not file.filename:
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

        upload_uuid = uuid.uuid4()
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = ".bin"

        final_file_path = f"image/{upload_uuid}{ext}"
        final_full_path = IMAGE_FOLDER / f"{upload_uuid}{ext}"

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

        return ImageUploadResponse(upload_id=result.id)

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="upload_scenario_image",
            request=http_request,
        )
        raise


@router.get("/{upload_id}/download", response_model=None)
async def download_image(
    upload_id: str,
    http_request: Request,
) -> FileResponse:
    """Download an image file by upload ID."""
    try:
        upload_id_uuid = uuid.UUID(upload_id)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await get_upload(conn, upload_id_uuid)

        if result is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        stored_path = result.file_path or ""
        file_path = os.path.join(IMAGE_FOLDER, os.path.basename(stored_path))

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Image file not found")

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
            operation="download_scenario_image",
            request=http_request,
        )
        raise
