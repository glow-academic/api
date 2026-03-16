"""Scenario video uploads — upload, download, and TUS resumable."""

import base64
import json
import os
import shutil
import urllib.parse
import uuid

from fastapi import APIRouter, HTTPException, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.infra.globals import (
    TUS_UPLOADS_DIR,
    VIDEO_FOLDER,
    get_pool,
    get_redis_client,
)
from app.tools.entries.uploads.create import create_upload
from app.tools.entries.uploads.get import get_upload
from app.utils.cache.invalidate_tags import invalidate_tags
from app.utils.error.handle_route_error import handle_route_error
from app.utils.logging.db_logger import get_logger
from app.utils.mime.get_content_type import get_content_type

logger = get_logger(__name__)

router = APIRouter(prefix="/video", tags=["video"])

TUS_HEADERS = {
    "Tus-Resumable": "1.0.0",
    "Tus-Version": "1.0.0",
    "Tus-Extension": "creation,termination,creation-with-upload",
    "Tus-Max-Size": "1073741824",  # 1GB
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, HEAD, PATCH, OPTIONS",
    "Access-Control-Allow-Headers": "Tus-Resumable, Upload-Length, Upload-Metadata, Upload-Offset, Content-Type",
    "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length, Location",
    "Access-Control-Max-Age": "86400",
}


# ---------------------------------------------------------------------------
# Multipart upload (simple path)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# TUS resumable upload flow
# ---------------------------------------------------------------------------


@router.options("/discover")
async def tus_discover(request: Request) -> Response:
    """TUS protocol discovery."""
    return Response(headers=TUS_HEADERS)


@router.options("/discover/{upload_id}")
async def tus_discover_upload(upload_id: str, request: Request) -> Response:
    """TUS protocol discovery for a specific upload."""
    return Response(headers=TUS_HEADERS)


@router.post("/create")
async def tus_create(request: Request) -> Response:
    """Create a TUS upload session."""
    if request.headers.get("Tus-Resumable") != "1.0.0":
        return Response(status_code=412, headers={"Tus-Version": "1.0.0"})

    upload_length = request.headers.get("Upload-Length")
    if not upload_length:
        return Response(status_code=400, content="Missing Upload-Length header")

    # Parse metadata
    metadata = {}
    if "Upload-Metadata" in request.headers:
        for kv in request.headers["Upload-Metadata"].split(","):
            if " " in kv:
                k, v = kv.strip().split(" ", 1)
                metadata[k] = base64.b64decode(v).decode("utf-8")

    app_prefix = os.getenv("APP_PREFIX", "").strip("/")

    # Create upload directory and files
    upload_id = str(uuid.uuid4())
    upload_dir = TUS_UPLOADS_DIR / upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)

    with open(upload_dir / "metadata.json", "w") as f:
        json.dump(metadata, f)

    with open(upload_dir / "file", "wb") as f:
        pass

    with open(upload_dir / "info", "w") as f:
        f.write(f"length:{upload_length}\noffset:0")

    if app_prefix:
        location = f"/{app_prefix}/v5/scenarios/video/{upload_id}"
    else:
        location = f"/v5/scenarios/video/{upload_id}"

    # Handle creation-with-upload if Content-Length > 0
    if request.headers.get("Content-Length", "0") != "0":
        chunk = await request.body()

        info = {}
        with open(upload_dir / "info") as f:
            for line in f:
                k, v = line.strip().split(":", 1)
                info[k] = v

        with open(upload_dir / "file", "ab") as f:
            f.write(chunk)

        new_offset = int(info.get("offset", "0")) + len(chunk)
        with open(upload_dir / "info", "w") as f:
            f.write(f"length:{info.get('length', '0')}\noffset:{new_offset}")

        return Response(
            status_code=201,
            headers={
                "Location": location,
                "Tus-Resumable": "1.0.0",
                "Upload-Offset": str(new_offset),
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length, Location",
            },
        )

    return Response(
        status_code=201,
        headers={
            "Location": location,
            "Tus-Resumable": "1.0.0",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length, Location",
        },
    )


@router.head("/{upload_id}/status")
async def tus_status(upload_id: str, request: Request) -> Response:
    """Get current upload offset and length."""
    upload_dir = TUS_UPLOADS_DIR / upload_id

    if not upload_dir.exists():
        return Response(status_code=404)

    info = {}
    with open(upload_dir / "info") as f:
        for line in f:
            k, v = line.strip().split(":", 1)
            info[k] = v

    return Response(
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": info.get("offset", "0"),
            "Upload-Length": info.get("length", "0"),
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length, Location",
        }
    )


@router.patch("/{upload_id}/chunk")
async def tus_chunk(upload_id: str, request: Request) -> Response:
    """Append a chunk to an in-progress upload."""
    if request.headers.get("Tus-Resumable") != "1.0.0":
        return Response(status_code=412, headers={"Tus-Version": "1.0.0"})

    if request.headers.get("Content-Type") != "application/offset+octet-stream":
        return Response(status_code=415)

    expected_offset = request.headers.get("Upload-Offset")
    if not expected_offset:
        return Response(status_code=400, content="Missing Upload-Offset header")

    chunk = await request.body()

    upload_dir = TUS_UPLOADS_DIR / upload_id

    if not upload_dir.exists():
        return Response(status_code=404)

    info = {}
    with open(upload_dir / "info") as f:
        for line in f:
            k, v = line.strip().split(":", 1)
            info[k] = v

    if expected_offset != info.get("offset"):
        return Response(status_code=409)

    with open(upload_dir / "file", "ab") as f:
        f.write(chunk)

    new_offset = int(info.get("offset", "0")) + len(chunk)
    with open(upload_dir / "info", "w") as f:
        f.write(f"length:{info.get('length', '0')}\noffset:{new_offset}")

    return Response(
        headers={
            "Tus-Resumable": "1.0.0",
            "Upload-Offset": str(new_offset),
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Expose-Headers": "Tus-Resumable, Upload-Offset, Upload-Length, Location",
        }
    )


class FinalizeUploadResponse(BaseModel):
    upload_id: uuid.UUID


@router.post("/{upload_id}/finalize", response_model=FinalizeUploadResponse)
async def finalize_upload(
    upload_id: str,
    http_request: Request,
    response: Response,
) -> FinalizeUploadResponse:
    """Finalize a TUS upload — move to permanent storage and create DB record."""
    tags = ["uploads"]

    try:
        upload_dir = TUS_UPLOADS_DIR / upload_id

        if not upload_dir.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Upload with uploadId {upload_id} not found",
            )

        file_path = upload_dir / "file"

        if not file_path.exists() or file_path.stat().st_size == 0:
            raise HTTPException(
                status_code=400,
                detail="Upload file is missing or empty",
            )

        metadata_path = upload_dir / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            with open(metadata_path) as f:
                metadata = json.load(f)

        filename = metadata.get("filename", "unknown")
        file_size = file_path.stat().st_size

        upload_uuid = uuid.uuid4()
        _, ext = os.path.splitext(filename)
        if not ext:
            ext = ".bin"

        final_file_path = f"video/{upload_uuid}{ext}"
        final_full_path = VIDEO_FOLDER / f"{upload_uuid}{ext}"

        shutil.copy2(str(file_path), str(final_full_path))

        content_type = metadata.get("filetype") or get_content_type(filename)

        profile_id = http_request.state.profile_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        session_id = http_request.state.session_id
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required.",
            )

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await create_upload(
                conn,
                session_id=uuid.UUID(session_id),
                file_path=final_file_path,
                mime_type=content_type,
                size=file_size,
            )

        try:
            shutil.rmtree(str(upload_dir))
        except Exception as e:
            logger.warning(f"Failed to clean up upload directory: {str(e)}")

        await invalidate_tags(tags, redis=get_redis_client())
        response.headers["X-Invalidate-Tags"] = ",".join(tags)

        return FinalizeUploadResponse(upload_id=result.id)

    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="finalize_scenario_video",
            request=http_request,
        )


# ---------------------------------------------------------------------------
# Download (with HTTP Range support for video seeking)
# ---------------------------------------------------------------------------


def _create_range_streaming_response(
    file_path: str,
    content_type: str,
    range_header: str | None,
    content_disposition: str,
) -> Response:
    """Create a streaming response with HTTP Range support for video seeking."""
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
async def download_video(
    upload_id: str,
    http_request: Request,
) -> Response:
    """Download a video file by upload ID with range support for seeking."""
    try:
        upload_id_uuid = uuid.UUID(upload_id)

        pool = get_pool()
        async with pool.acquire() as conn:
            result = await get_upload(conn, upload_id_uuid)

        if result is None:
            raise HTTPException(status_code=404, detail="Upload not found")

        stored_path = result.file_path or ""
        file_path = os.path.join(VIDEO_FOLDER, os.path.basename(stored_path))

        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Video file not found")

        content_type = get_content_type(result.file_path or "", result.mime_type or "")

        filename = os.path.basename(result.file_path or "")
        encoded_filename = urllib.parse.quote(filename, safe="")
        content_disposition = f"inline; filename=\"{encoded_filename}\"; filename*=UTF-8''{encoded_filename}"

        range_header = http_request.headers.get("range")
        return _create_range_streaming_response(
            file_path=file_path,
            content_type=content_type,
            range_header=range_header,
            content_disposition=content_disposition,
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="download_scenario_video",
            request=http_request,
        )
        raise
