"""Canonical shared chat GET operation."""

from __future__ import annotations

from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.attempt.chat.context import resolve_chat_context
from app.infra.attempt.chat.permissions import CHAT_BUNDLE_RESOURCES
from app.infra.attempt.chat.sections import build_chat_get_result
from app.infra.common_context import resolve_common_context
from app.infra.tool_graph import score_tools
from app.infra.attempt.chat.types import GetChatRequest, GetChatResponse, SectionFilter

SECTIONS = [
    "names",
    "descriptions",
    "flags",
    "departments",
    "personas",
    "documents",
    "parameter_fields",
    "scenarios",
    "fields",
    "questions",
    "options",
    "videos",
    "images",
    "problem_statements",
    "objectives",
]


def _sf(filters: dict[str, SectionFilter | None], section: str, attr: str, default=None):
    sf = filters.get(section)
    if sf is None:
        return default
    return getattr(sf, attr, default)


async def get_chat_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    # Canonical flat kwargs (same pattern as get_persona_impl)
    id: UUID | None = None,
    chat_entry_id: UUID | None = None,
    attempt_id: UUID | None = None,
    draft_id: UUID | None = None,
    filters: dict[str, SectionFilter | None] | None = None,
    bypass_cache: bool = False,
    # Accept request object for backward compat (HTTP routes)
    request: GetChatRequest | None = None,
    **_kwargs,
) -> GetChatResponse:
    """Resolve the canonical chat bundle response for any surface."""
    f = filters or {}
    if request is not None:
        id = id or request.id or request.chat_entry_id
        chat_entry_id = chat_entry_id or request.chat_entry_id or request.id
        attempt_id = attempt_id or request.attempt_id
        draft_id = draft_id or request.draft_id
        f = {
            section: getattr(request, section, None)
            for section in SECTIONS
        }
    chat_entry_id = chat_entry_id or id

    common = await resolve_common_context(
        pool,
        redis,
        profile_id=profile_id,
        session_id=session_id,
        bypass_cache=bypass_cache,
    )

    if common is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # Chat is an attempt-scoped resource — use the canonical attempt group.
    from app.infra.attempt.group import group_attempt_impl
    group_result = await group_attempt_impl(
        pool, redis,
        profile_id=profile_id,
        session_id=session_id,
        include_history=False,
    )
    group_id = group_result.group_id

    context = await resolve_chat_context(
        pool,
        redis,
        group_id=group_id,
        chat_entry_id=chat_entry_id,
        draft_id=draft_id,
        profile=common.profile,
        names_search=_sf(f, "names", "search"),
        description_search=_sf(f, "descriptions", "search"),
        flags_search=_sf(f, "flags", "search"),
        departments_search=_sf(f, "departments", "search"),
        persona_search=_sf(f, "personas", "search"),
        document_search=_sf(f, "documents", "search"),
        scenario_search=_sf(f, "scenarios", "search"),
        field_search=_sf(f, "fields", "search"),
        problem_statement_search=_sf(f, "problem_statements", "search"),
        objective_search=_sf(f, "objectives", "search"),
        image_search=_sf(f, "images", "search"),
        video_search=_sf(f, "videos", "search"),
        question_search=_sf(f, "questions", "search"),
        option_search=_sf(f, "options", "search"),
        names_limit=_sf(f, "names", "limit"),
        descriptions_limit=_sf(f, "descriptions", "limit"),
        flags_limit=_sf(f, "flags", "limit"),
        departments_limit=_sf(f, "departments", "limit"),
        personas_limit=_sf(f, "personas", "limit"),
        documents_limit=_sf(f, "documents", "limit"),
        scenarios_limit=_sf(f, "scenarios", "limit"),
        fields_limit=_sf(f, "fields", "limit"),
        parameter_fields_limit=_sf(f, "parameter_fields", "limit"),
        questions_limit=_sf(f, "questions", "limit"),
        options_limit=_sf(f, "options", "limit"),
        videos_limit=_sf(f, "videos", "limit"),
        images_limit=_sf(f, "images", "limit"),
        problem_statements_limit=_sf(f, "problem_statements", "limit"),
        objectives_limit=_sf(f, "objectives", "limit"),
        persona_show_selected=_sf(f, "personas", "selected"),
        document_show_selected=_sf(f, "documents", "selected"),
        bypass_cache=bypass_cache,
    )

    scores = score_tools(common.tool_graph, CHAT_BUNDLE_RESOURCES)
    return build_chat_get_result(
        common=common,
        context=context,
        scores=scores,
        chat_entry_id=chat_entry_id,
        attempt_id=attempt_id,
        include={s: _sf(f, s, "include") is not False for s in SECTIONS},
        selected_only={s: _sf(f, s, "selected") or False for s in SECTIONS},
        suggested_only={s: _sf(f, s, "suggested") or False for s in SECTIONS},
    )
