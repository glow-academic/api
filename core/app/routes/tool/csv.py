"""POST /tool/csv — thin HTTP adapter over parse_tool_csv_impl."""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile

from app.infra.tool.csv import (
    CsvParseError,
    ParseToolCsvApiResponse,
    parse_tool_csv_impl,
)
from app.infra.tool.group import group_tool_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/csv", response_model=ParseToolCsvApiResponse)
async def parse_tool_csv(
    file: UploadFile,
    http_request: Request,
    idempotency_key: UUID | None = Form(None),
) -> ParseToolCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        file_bytes = await file.read()
        file_name = file.filename or "file.csv"
        content_type = file.content_type or "text/csv"
        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_tool_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        async def _runner() -> ParseToolCsvApiResponse:
            return await parse_tool_csv_impl(
                pool,
                session_id=session_id,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=content_type,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="tool",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="csv",
            # Fingerprint on filename + content hash so a retry of the SAME
            # upload replays, and a different file under the same key → 409.
            arguments={
                "file_name": file_name,
                "content_sha256": hashlib.sha256(file_bytes).hexdigest(),
            },
            response_model=ParseToolCsvApiResponse,
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
            operation="parse_tool_csv",
            request=http_request,
        )
