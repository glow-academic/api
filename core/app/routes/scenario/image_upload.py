"""Scenario image upload endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.scenario.image_upload.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.shared_types import read_upload_bounded
from app.infra.scenario.group import group_scenario_impl
from app.infra.scenario.image_upload import image_upload_scenario_impl
from app.infra.scenario.types import ImageUploadScenarioApiResponse
from app.utils.error.handle_route_error import handle_route_error
from app.utils.mime.get_content_type import get_content_type

router = APIRouter()

ALLOWED_IMAGE_TYPES = {
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/svg+xml",
    "image/webp",
    "image/bmp",
    "image/tiff",
}


@router.post("/image_upload", response_model=ImageUploadScenarioApiResponse)
async def upload_image(
    http_request: Request,
    response: Response,
    file: UploadFile | None = File(None),
    name: str | None = None,
    description: str | None = None,
    idempotency_key: UUID | None = Form(None),
    soft: bool = Form(False),
    accept: bool | None = Form(None),
) -> ImageUploadScenarioApiResponse:
    """Upload an image for later use in scenarios (soft/accept dormant flow)."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        is_ack = accept is not None and idempotency_key is not None

        if is_ack:
            # Ack call: no file. Carry `accept` in arguments so the replay gate's
            # _is_bare_ack skips it (don't replay the propose receipt).
            file_bytes = None
            filename = None
            content_type = None
            arguments: dict = {"accept": accept}
        else:
            # ── Validate file ──────────────────────────────────────────────
            if file is None or not file.filename:
                raise HTTPException(status_code=400, detail="Missing filename")

            content_type = file.content_type or get_content_type(file.filename)
            if content_type not in ALLOWED_IMAGE_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported image type: {content_type}",
                )

            # Bounded read: abort the moment the body crosses the cap so a
            # streamed multi-GB upload can't exhaust memory/disk before being
            # rejected (image/video/file bodies are inherently large).
            file_bytes = await read_upload_bounded(
                file,
                make_error=lambda msg: HTTPException(status_code=413, detail=msg),
            )
            if not file_bytes:
                raise HTTPException(status_code=400, detail="Empty file")
            filename = file.filename
            arguments = {
                "filename": filename,
                "content_type": content_type,
                "size": len(file_bytes),
                "name": name,
                "description": description,
            }

        # ── Run with audit ─────────────────────────────────────────────
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_scenario_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        # ``call_id`` is threaded in by the audit wrapper (signature opt-in) —
        # it's the server-minted calls_entry id the soft ledger keys on.
        async def _runner(call_id: UUID | None = None) -> ImageUploadScenarioApiResponse:
            return await image_upload_scenario_impl(
                pool,
                redis,
                profile_id=profile_id,
                session_id=session_id,
                file_bytes=file_bytes,
                filename=filename,
                content_type=content_type,
                name=name,
                description=description,
                soft=soft,
                accept=accept,
                idempotency_key=idempotency_key,
                call_id=call_id,
            )

        response_data = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            operation="image_upload",
            arguments=arguments,
            response_model=ImageUploadScenarioApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=idempotency_key,  # idempotency replay gate
            group_id=group_id,
        )

        response.headers["X-Invalidate-Tags"] = "uploads,resources,images"
        return response_data
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="image_upload_scenario",
            request=http_request,
        )
