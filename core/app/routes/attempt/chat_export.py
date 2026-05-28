"""Chat export endpoint — single-item CSV export for one chat entry.

Thin HTTP adapter over ``export_chat_impl``: resolves the session-windowed
group for audit linking, then runs the export inside the standard audit +
idempotency wrapper. Parallels ``/attempt/export`` (artifact-level) but
scopes to one chat entry, returning a base64 CSV envelope.
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request

from app.infra.attempt.chat.export import export_chat_impl
from app.infra.attempt.chat.types import (
    ExportChatApiRequest,
    ExportChatApiResponse,
)
from app.infra.attempt.group import group_attempt_impl
from app.infra.events.audit import run_artifact_operation_with_audit
from app.infra.globals import get_pool, get_redis_client, get_upload_folder
from app.utils.error.handle_route_error import handle_route_error

router = APIRouter()


@router.post("/chat_export", response_model=ExportChatApiResponse)
async def chat_export(
    body: ExportChatApiRequest,
    http_request: Request,
) -> ExportChatApiResponse:
    """Export a single chat entry as a denormalized CSV row."""
    try:
        profile_id = http_request.state.profile_id
        session_id = http_request.state.session_id
        if not profile_id:
            raise HTTPException(
                status_code=401,
                detail="Profile ID is required. Please sign in again.",
            )
        if not session_id:
            raise HTTPException(
                status_code=401,
                detail="Session ID is required. Please sign in again.",
            )

        pool = get_pool()
        redis = get_redis_client()

        # Resolve the time-windowed group for audit linking — same pattern as
        # ``/attempt/export`` and ``/attempt/chat_get``. ``export_chat_impl``
        # also requires ``group_id`` as a positional kwarg.
        group_result = await group_attempt_impl(
            pool, redis,
            profile_id=cast(UUID, profile_id),
            session_id=session_id,
            id_only=True,
        )
        group_id = group_result.group_id

        async def _runner() -> ExportChatApiResponse:
            return await export_chat_impl(
                pool,
                redis,
                profile_id=cast(UUID, profile_id),
                chat_entry_id=body.chat_entry_id,
                group_id=group_id,
                attempt_id=body.attempt_id,
                draft_id=body.draft_id,
            )

        return await run_artifact_operation_with_audit(
            pool,
            redis,
            artifact="attempt",
            profile_id=cast(UUID, profile_id),
            session_id=cast(UUID, session_id),
            group_id=group_id,
            operation="chat_export",
            arguments=body.model_dump(mode="json"),
            response_model=ExportChatApiResponse,
            runner=_runner,
            upload_folder=get_upload_folder(),
            operation_key=body.snapshot_key,  # read snapshot
        )
    except HTTPException:
        raise
    except Exception as e:
        handle_route_error(
            error=e,
            route_path=http_request.url.path,
            operation="chat_export",
            sql_query=None,
            sql_params=None,
            request=http_request,
        )
