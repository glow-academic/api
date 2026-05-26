"""Document drafts list/search — composable infra architecture.

Composes existing black-box tools — no inline SQL:
  1. resolve_profile_identity_context — caller's profiles_id
  2. search_document_drafts — declarative filters (name ILIKE, date window,
     pagination) on the entry table + connections

Single function powers both:
  - LLM dispatch (artifact, "drafts") via INFRA_OPS auto-discovery
  - FE ``POST /document/drafts`` HTTP route

Both consumers receive the same ``GetDocumentDraftsApiResponse`` shape; the
LLM render template iterates ``entries[]`` like the FE list page does.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.infra.document.types import GetDocumentDraftsApiResponse
from app.tools.entries.document_drafts.search import search_document_drafts


async def list_document_drafts_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_limit: int = 50,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> GetDocumentDraftsApiResponse:
    """List/search document drafts owned by the current profile."""
    with timed("profile"):
        profile = await resolve_profile_identity_context(
            pool, profile_id, redis, session_id=session_id, bypass_cache=bypass_cache,
        )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    with timed("query"):
     async with pool.acquire() as conn:
        drafts = await search_document_drafts(
            conn,
            redis, profile_ids=[profile.profiles_id],
            session_ids=[session_id] if session_id else None,
            name=search,
            date_from=date_from,
            date_to=date_to,
            limit=page_limit,
            offset=page_offset,
        )

    return GetDocumentDraftsApiResponse(entries=drafts)
