"""Document delete endpoint — composable infra architecture.

Thin route handler. Core logic lives in app.infra.document.delete.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from app.infra.document.delete import delete_document_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.infra.document.types import (
    DeleteDocumentApiRequest,
    DeleteDocumentApiResponse,
)
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/delete", response_model=DeleteDocumentApiResponse)
async def delete_document(
    request: DeleteDocumentApiRequest,
    http_request: Request,
    response: Response,
) -> DeleteDocumentApiResponse:
    """Bulk delete documents — composable infra architecture."""
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

        async def _runner() -> DeleteDocumentApiResponse:
            return await delete_document_impl(
                pool,
                redis,
                profile_id=profile_id,
                document_ids=request.document_ids,
                session_id=session_id,
            )

        result = await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="document",
            profile_id=profile_id,
            session_id=session_id,
            operation="delete",
            arguments=request.model_dump(mode="json"),
            response_model=DeleteDocumentApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
        )

        response.headers["X-Invalidate-Tags"] = ",".join(tags)
        return result
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="delete_document",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
