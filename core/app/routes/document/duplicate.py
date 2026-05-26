"""Document duplicate endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.document.duplicate.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.document.duplicate import duplicate_document_impl
from app.infra.document.group import group_document_impl
from app.infra.document.types import (
    DuplicateDocumentApiRequest,
    DuplicateDocumentApiResponse,
)
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post(
    "/duplicate",
    response_model=DuplicateDocumentApiResponse,
)
async def duplicate_document(
    request: DuplicateDocumentApiRequest,
    http_request: Request,
    response: Response,
) -> DuplicateDocumentApiResponse:
    """Duplicate a document — composable infra architecture."""
    tags = ["documents"]

    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve time-windowed group for audit linking
        group_id = None
        if session_id:
            group_result = await group_document_impl(
                pool, redis, profile_id=profile_id, session_id=session_id,
                id_only=True,
            )
            group_id = group_result.group_id

        is_ack = request.accept is not None and request.idempotency_key is not None
        premint_call_id = None if is_ack else request.idempotency_key

        async def _runner() -> DuplicateDocumentApiResponse:
            return await duplicate_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                id=request.document_id,
                session_id=session_id,
                soft=request.soft,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            group_id=group_id,
            operation="duplicate",
            arguments=request.model_dump(mode="json"),
            response_model=DuplicateDocumentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=request.idempotency_key,  # idempotency replay gate
            call_id=premint_call_id,  # pre-mint calls_entry with client key (HTTP soft FK)
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="duplicate_document",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
