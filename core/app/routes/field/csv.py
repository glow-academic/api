"""POST /field/csv — thin HTTP adapter over parse_field_csv_impl."""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.infra.field.csv import (
    CsvParseError,
    ParseFieldCsvApiResponse,
    parse_field_csv_impl,
)
from app.infra.field.group import group_field_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/csv", response_model=ParseFieldCsvApiResponse)
async def parse_field_csv(
    http_request: Request,
    file: UploadFile | None = File(None),
    idempotency_key: UUID | None = Form(None),
    soft: bool = Form(False),
    accept: bool | None = Form(None),
) -> ParseFieldCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_field_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = accept is not None and idempotency_key is not None

        if is_ack:
            # Ack call: no file. Carry `accept` in arguments so the gate skips it.
            file_bytes = None
            file_name = None
            content_type = None
            arguments: dict = {"accept": accept}
        else:
            if file is None or not file.filename:
                raise HTTPException(status_code=400, detail="Missing CSV file")
            # Read file bytes at route boundary (UploadFile can only be read once)
            file_bytes = await file.read()
            file_name = file.filename or "file.csv"
            content_type = file.content_type or "text/csv"
            arguments = {
                "file_name": file_name,
                "content_sha256": hashlib.sha256(file_bytes).hexdigest(),
            }

        async def _runner(call_id: UUID | None = None) -> ParseFieldCsvApiResponse:
            return await parse_field_csv_impl(
                pool,
                session_id=session_id,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
                soft=soft,
                accept=accept,
                idempotency_key=idempotency_key,
                call_id=call_id,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="field",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="csv",
            arguments=arguments,
            response_model=ParseFieldCsvApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=idempotency_key,  # idempotency replay gate
        )
    except CsvParseError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="parse_field_csv",
            request=http_request,
        )
