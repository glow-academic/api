"""Invocation export endpoint — composable infra architecture."""

from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.infra.globals import get_pool, get_redis_client
from app.infra.invocation.export import export_invocation_impl
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.invocation.types import ExportInvocationApiResponse

router = APIRouter()


class ExportInvocationApiRequest(BaseModel):
    """Request model for invocation export."""

    test_id: UUID
    invocation_entry_id: UUID | None = None
    draft_id: UUID | None = None


@router.post("/export", response_model=ExportInvocationApiResponse)
async def export_invocation(
    body: ExportInvocationApiRequest,
    http_request: Request,
) -> ExportInvocationApiResponse:
    """Export a single invocation as a clean, denormalized CSV."""
    profile_id = http_request.state.profile_id
    session_id = http_request.state.session_id
    pool = get_pool()
    redis = get_redis_client()
    identity = await resolve_profile_identity_context(
        pool,
        profile_id,
        redis,
        session_id=session_id,
        draft_id=body.draft_id,
        test_id=body.test_id,
    )
    group_id = identity.group_id if identity else None
    if group_id is None:
        raise ValueError("Group ID could not be resolved for invocation export")

    return await export_invocation_impl(
        pool,
        redis,
        profile_id=profile_id,
        test_id=body.test_id,
        group_id=group_id,
        invocation_entry_id=body.invocation_entry_id,
        draft_id=body.draft_id,
    )
