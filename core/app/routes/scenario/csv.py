"""Scenario CSV parse endpoint — thin HTTP adapter.

Core logic lives in app.infra.scenario.csv.
"""

from __future__ import annotations

import hashlib
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.shared_types import MAX_CSV_UPLOAD_BYTES, read_upload_bounded
from app.infra.scenario.csv import ParseScenarioCsvApiResponse, parse_scenario_csv_impl
from app.infra.scenario.group import group_scenario_impl
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/csv", response_model=ParseScenarioCsvApiResponse)
async def parse_scenario_csv(
    http_request: Request,
    file: UploadFile | None = File(None),
    idempotency_key: UUID | None = Form(None),
    soft: bool = Form(False),
    accept: bool | None = Form(None),
) -> ParseScenarioCsvApiResponse:
    """Parse a CSV file and return mapped items for preview."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
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
            # Read file bytes at route boundary (UploadFile can only be read
            # once), bounded: abort the moment the body crosses the cap so a
            # streamed multi-GB upload can't exhaust memory before the row-cap
            # parse even runs.
            file_bytes = await read_upload_bounded(
                file,
                make_error=lambda msg: HTTPException(status_code=413, detail=msg),
                max_bytes=MAX_CSV_UPLOAD_BYTES,
            )
            file_name = file.filename or "file.csv"
            content_type = file.content_type or "text/csv"
            arguments = {
                "file_name": file_name,
                "content_sha256": hashlib.sha256(file_bytes).hexdigest(),
            }

        async def _runner(call_id: UUID | None = None) -> ParseScenarioCsvApiResponse:
            return await parse_scenario_csv_impl(
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
            artifact="scenario",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="csv",
            arguments=arguments,
            response_model=ParseScenarioCsvApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=idempotency_key,  # idempotency replay gate
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="parse_scenario_csv",
            request=http_request,
        )
