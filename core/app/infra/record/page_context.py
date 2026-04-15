"""Record page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the record page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Permission evaluation — concrete booleans for THIS caller
  3. API operations — all public route handlers introspected
  4. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
)
from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

_PAGE_METADATA = PageMetadataConfig(
    list_title="Records",
    list_description="View per-profile performance dashboards.",
    detail_title="Record",
    detail_description="View profile performance with attempt history and trends.",
    new_title="Record",
    new_description="View profile performance with attempt history and trends.",
)


async def page_context_record_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Record page context — superset of docs_record_impl.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Evaluate caller permissions using profile data
      3. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 3: Evaluate caller permissions ------------------------------------
    # Record is analytics — no entity-level create/draft/duplicate.
    # CallerPermissions still populated for sidebar/nav consistency.

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.record.export import export_record
    from app.routes.record.get import get_record
    from app.routes.record.refresh import record_refresh
    from app.routes.record.search import search_record

    return ComposedContextResponse(
        name="record",
        type="analytics",
        description=(
            "Record analytics provides per-profile performance dashboards "
            "with attempt history, scoring trends, and progress tracking."
        ),
        artifact=None,
        entries=[],
        resources=[],
        permission_docs=[],
        api_operations=[
            get_operation_info(
                get_record,
                description="POST /get — Get record dashboard for a specific profile.",
            ),
            get_operation_info(
                search_record,
                description="POST /search — Search record history entries.",
            ),
            get_operation_info(
                record_refresh,
                description="POST /refresh — Refresh record materialized views.",
            ),
            get_operation_info(
                export_record,
                description="POST /export — Export record data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
