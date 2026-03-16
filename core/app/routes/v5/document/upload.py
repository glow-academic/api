"""Document upload — single streaming endpoint for all modalities."""

import os
import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from app.infra.globals import UPLOAD_FOLDER, get_pool, get_redis_client
from app.tools.entries.uploads.create import create_upload
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

# Subdirectory by broad media category
_SUBDIR_BY_TYPE: dict[str, str] = {
    "audio": "audio",
    "image": "image",
    "video": "video",
}


def _resolve_subdir(mime_type: str) -> str:
    """Pick the storage subdirectory from the mime type prefix."""
    prefix = mime_type.split("/")[0]
    return _SUBDIR_BY_TYPE.get(prefix, "")


class UploadResponse(BaseModel):
    upload_id: uuid.UUID


@router.post("/upload", response_model=UploadResponse)
async def upload(http_request: Request, response: Response) -> UploadResponse:
    """Stream-upload any file.

    Headers:
      Content-Type: the file's actual MIME type
      X-Filename: original filename (for extension + display)
      Content-Length: file size in bytes (optional but recommended)
    Body: raw file bytes (streamed, not multipart).
    """
    tags = ["uploads"]

    try:
        filename = http_request.headers.get("x-filename", "unknown.bin")
        content_type = http_request.headers.get("content-type", "application/octet-stream")

        # Infer content type from filename if generic
        if content_type == "application/octet-stream":
            content_type = get_content_type(filename)

        _, ext = os.path.splitext(filename)
        if not ext:
            ext = ".bin"

        upload_uuid = uuid.uuid4()
        subdir = _resolve_subdir(content_type)

        if subdir:
            dest_dir = UPLOAD_FOLDER / subdir
            dest_dir.mkdir(parents=True, exist_ok=True)
            relative_path = f"{subdir}/{upload_uuid}{ext}"
        else:
            relative_path = f"{upload_uuid}{ext}"

        full_path = UPLOAD_FOLDER / relative_path
        file_size = 0

        # Stream body to disk in chunks — never buffer the whole file
        with open(full_path, "wb") as f:
            async for chunk in http_request.stream():
                f.write(chunk)
                file_size += len(chunk)

        if file_size == 0:
            os.unlink(full_path)
            raise HTTPException(status_code=400, detail="Empty file")

        session_id = getattr(http_request.state, "session_id", None)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await create_upload(
                conn,
                session_id=uuid.UUID(session_id) if session_id else uuid.UUID(int=0),
                file_path=relative_path,
                mime_type=content_type,
                size=file_size,
            )

        await invalidate_tags(tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return UploadResponse(upload_id=result.id)

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="upload_document",
            request=http_request,
        )
        raise
