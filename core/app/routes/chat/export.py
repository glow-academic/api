"""Chat export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.infra.attempt.chat.export import export_chat_impl
from app.infra.globals import get_pool, get_redis_client
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.attempt.chat.types import ExportChatApiResponse

router = APIRouter()


class ExportChatApiRequest(BaseModel):
    """Request model for chat export."""

    chat_entry_id: UUID
    attempt_id: UUID | None = None
    draft_id: UUID | None = None


@router.post("/export", response_model=ExportChatApiResponse)
async def export_chat(
    body: ExportChatApiRequest,
    http_request: Request,
) -> ExportChatApiResponse:
    """Export a single chat as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()
    from app.infra.attempt.group import group_attempt_impl
    group_result = await group_attempt_impl(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )
    group_id = group_result.group_id

    return await export_chat_impl(
        pool,
        redis,
        profile_id=profile_id,
        chat_entry_id=body.chat_entry_id,
        group_id=group_id,
        attempt_id=body.attempt_id,
        draft_id=body.draft_id,
    )
