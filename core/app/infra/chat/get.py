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
    # Canonical flat kwargs (same pattern as get_persona_impl)
    chat_entry_id: UUID | None = None,
    attempt_id: UUID | None = None,
    draft_id: UUID | None = None,
    description_search: str | None = None,
    persona_search: str | None = None,
    document_search: str | None = None,
    problem_statement_search: str | None = None,
    image_search: str | None = None,
    video_search: str | None = None,
    question_search: str | None = None,
    option_search: str | None = None,
    persona_show_selected: bool | None = None,
    document_show_selected: bool | None = None,
    bypass_cache: bool = False,
    # Accept request object for backward compat (HTTP routes)
    request: GetChatRequest | None = None,
    **_kwargs,
) -> GetChatResponse:
    """Resolve the canonical chat bundle response for any surface."""
    # If request object provided, extract fields from it
    if request is not None:
        chat_entry_id = chat_entry_id or request.chat_entry_id
        attempt_id = attempt_id or request.attempt_id
        draft_id = draft_id or request.draft_id
        description_search = description_search or request.description_search
        persona_search = persona_search or request.persona_search
        document_search = document_search or request.document_search
        problem_statement_search = problem_statement_search or request.problem_statement_search
        image_search = image_search or request.image_search
        video_search = video_search or request.video_search
        question_search = question_search or request.question_search
        option_search = option_search or request.option_search
        persona_show_selected = persona_show_selected if persona_show_selected is not None else request.persona_show_selected
        document_show_selected = document_show_selected if document_show_selected is not None else request.document_show_selected

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        attempt_id=attempt_id,
        draft_id=draft_id,
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
        chat_entry_id=chat_entry_id,
        draft_id=draft_id,
        profile=common.profile,
        description_search=description_search,
        persona_search=persona_search,
        document_search=document_search,
        problem_statement_search=problem_statement_search,
        image_search=image_search,
        video_search=video_search,
        question_search=question_search,
        option_search=option_search,
        persona_show_selected=persona_show_selected,
        document_show_selected=document_show_selected,
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, CHAT_BUNDLE_RESOURCES)
    return build_chat_get_result(
        context=context,
        scores=scores,
        group_id=group_id,
        chat_entry_id=chat_entry_id,
        attempt_id=attempt_id,
    )
