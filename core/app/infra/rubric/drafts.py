"""Rubric drafts list/search — composable infra architecture.

Thin wrapper that delegates to the shared ``search_drafts_impl`` black
box (which queries ``rubric_drafts_mv`` with the indexed
``lower(name)`` prefix filter + date/pagination). One operation
``drafts`` covers both the FE list page and the LLM-callable searchable
tool — there are no separate dispatch paths.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.drafts.search import (
    SearchDraftsResponse,
    search_drafts_impl,
)


async def list_rubric_drafts_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_size: int = 50,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> SearchDraftsResponse:
    """List/search rubric drafts owned by the current profile."""
    return await search_drafts_impl(
        pool,
        redis,
        artifact_type="rubric",
        profile_id=profile_id,
        session_id=session_id,
        search=search,
        date_from=date_from,
        date_to=date_to,
        page_size=page_size,
        page_offset=page_offset,
        own_only=True,
    )
