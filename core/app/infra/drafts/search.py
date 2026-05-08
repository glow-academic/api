"""Shared draft search — searchable across every artifact's drafts MV.

Each artifact has a ``<artifact>_drafts_mv`` view (kept fresh by the
canonical refresh queue) with a uniform shape:

    id, created_at, generated, mcp, active, session_id, name

This module dispatches by ``artifact_type`` to the right MV. Filters:

  - ``search``        — case-insensitive prefix on ``name`` (uses the
                        ``<artifact>_drafts_mv_name_idx`` btree on
                        ``lower(name) text_pattern_ops``).
  - ``date_from``     — ``created_at >= …``
  - ``date_to``       — ``created_at <= …``
  - ``profile_id``    — restrict to drafts owned by this profile (joins
                        the ``<artifact>_drafts_profiles_connection``).
  - ``session_ids``   — restrict to specific sessions.

Returns lightweight rows (no junction hydration). For full draft state
the caller follows up with ``get_<artifact>_draft`` on a chosen id.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg
from fastapi import HTTPException
from pydantic import BaseModel, Field
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context

# Whitelist of artifact_type values we'll dispatch to. Validated against
# this set before any string interpolation so a caller can't slip in an
# arbitrary table name.
KNOWN_DRAFT_ARTIFACTS: frozenset[str] = frozenset({
    "agent", "auth", "chat", "cohort", "department", "document", "eval",
    "field", "invocation", "model", "parameter", "persona", "profile",
    "provider", "rubric", "scenario", "setting", "simulation", "tool",
})


class SearchDraftsItem(BaseModel):
    """One draft row in the search response."""

    draft_id: UUID = Field(..., description="The draft's ``<artifact>_drafts_entry`` id")
    name: str = Field("", description="Immutable draft label set at create time")
    session_id: UUID | None = Field(None, description="Session that originated the draft")
    created_at: datetime = Field(..., description="Draft creation timestamp")
    mcp: bool = Field(False, description="True if the draft was MCP-originated")
    generated: bool = Field(False, description="True if the draft was AI-generated")


class SearchDraftsResponse(BaseModel):
    """Shared response — per-artifact wrappers subclass for OpenAPI naming."""

    actor_name: str | None = Field(None, description="Caller's display name")
    items: list[SearchDraftsItem] = Field(default_factory=list)
    total_count: int = Field(0, description="Number of items returned (not total available)")


async def search_drafts_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    artifact_type: str,
    profile_id: UUID,
    session_id: UUID | None = None,
    search: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page_size: int = 50,
    page_offset: int = 0,
    own_only: bool = True,
    **_kwargs,
) -> SearchDraftsResponse:
    """Search ``<artifact>_drafts_mv`` with filters.

    ``own_only=True`` joins the per-artifact ``profiles_connection`` and
    restricts to drafts the caller owns. Set False to surface every
    active draft (admin-style listing); permission gates upstream.
    """
    if artifact_type not in KNOWN_DRAFT_ARTIFACTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown artifact_type for drafts search: {artifact_type!r}",
        )

    profile = await resolve_profile_identity_context(
        pool, profile_id, redis, session_id=session_id,
    )
    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Build SQL ─────────────────────────────────────────────────────
    # ``artifact_type`` is whitelisted above, so f-string interpolation
    # of the table name is safe. All user-controlled values flow through
    # parameter placeholders.
    mv = f"{artifact_type}_drafts_mv"
    profiles_conn = f"{artifact_type}_drafts_profiles_connection"

    where: list[str] = ["d.active = true"]
    params: list[Any] = []

    def _bind(value: Any) -> str:
        params.append(value)
        return f"${len(params)}"

    if own_only:
        where.append(
            f"EXISTS (SELECT 1 FROM {profiles_conn} pc "
            f"WHERE pc.draft_id = d.id AND pc.profiles_id = "
            f"{_bind(profile.profiles_id)} AND pc.active = true)"
        )
    if search:
        # Case-insensitive prefix — uses the lower(name) text_pattern_ops index.
        where.append(f"lower(d.name) LIKE {_bind(search.lower() + '%')}")
    if session_id is not None:
        where.append(f"d.session_id = {_bind(session_id)}")
    if date_from is not None:
        where.append(f"d.created_at >= {_bind(date_from)}")
    if date_to is not None:
        where.append(f"d.created_at <= {_bind(date_to)}")

    sql = (
        f"SELECT d.id, d.name, d.session_id, d.created_at, d.mcp, d.generated\n"
        f"  FROM {mv} d\n"
        f" WHERE {' AND '.join(where)}\n"
        f" ORDER BY d.created_at DESC\n"
        f" LIMIT {_bind(page_size)} OFFSET {_bind(page_offset)}"
    )

    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    items = [
        SearchDraftsItem(
            draft_id=r["id"],
            name=r["name"] or "",
            session_id=r["session_id"],
            created_at=r["created_at"],
            mcp=r["mcp"],
            generated=r["generated"],
        )
        for r in rows
    ]
    return SearchDraftsResponse(
        actor_name=profile.name,
        items=items,
        total_count=len(items),
    )
