"""Scenario video upload."""

import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel

from app.infra.globals import VIDEO_FOLDER, get_pool, get_redis_client
from app.tools.entries.uploads.create import create_upload
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()


class VideoUploadResponse(BaseModel):
    upload_id: uuid.UUID


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile,
    http_request: Request,
    response: Response,
) -> VideoUploadResponse:
    """Upload a video file via multipart form-data."""
    tags = ["uploads"]

    try:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Missing filename")

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Empty file")

        upload_uuid = uuid.uuid4()
        _, ext = os.path.splitext(file.filename)
        if not ext:
            ext = ".bin"

        final_file_path = f"video/{upload_uuid}{ext}"
        final_full_path = VIDEO_FOLDER / f"{upload_uuid}{ext}"

        with open(final_full_path, "wb") as f:
            f.write(file_bytes)

        content_type = file.content_type or get_content_type(file.filename)
        file_size = len(file_bytes)

        session_id = getattr(http_request.state, "session_id", None)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await create_upload(
                conn,
                session_id=uuid.UUID(session_id) if session_id else uuid.UUID(int=0),
                file_path=final_file_path,
                mime_type=content_type,
                size=file_size,
            )

        await invalidate_tags(tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return VideoUploadResponse(upload_id=result.id)

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="upload_scenario_video",
            request=http_request,
        )
        raise
