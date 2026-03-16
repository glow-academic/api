"""Canonical shared chat GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.chat.context import resolve_chat_context
from app.infra.chat.permissions import CHAT_BUNDLE_RESOURCES
from app.infra.chat.sections import build_chat_get_result
from app.infra.common_context import resolve_common_context
from app.infra.tool_graph import score_tools
from app.infra.chat.types import GetChatRequest, GetChatResponse


async def get_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    request: GetChatRequest,
    bypass_cache: bool = False,
) -> GetChatResponse:
    """Resolve the canonical chat bundle response for any surface."""
    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        attempt_id=request.attempt_id,
        draft_id=request.draft_id,
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    group_id = common.profile.group_id
    if group_id is None:
        raise HTTPException(status_code=400, detail="Failed to resolve group context.")

    context = await resolve_chat_context(
        pool,
        redis,
        group_id=group_id,
        draft_id=request.draft_id,
        user_department_ids=common.profile.department_ids,
        description_search=request.description_search,
        persona_search=request.persona_search,
        document_search=request.document_search,
        problem_statement_search=request.problem_statement_search,
        image_search=request.image_search,
        video_search=request.video_search,
        question_search=request.question_search,
        option_search=request.option_search,
        persona_show_selected=request.persona_show_selected,
        document_show_selected=request.document_show_selected,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, CHAT_BUNDLE_RESOURCES)
    return build_chat_get_result(
        context=context,
        scores=scores,
        group_id=group_id,
        chat_entry_id=request.chat_entry_id,
        attempt_id=request.attempt_id,
    )
