"""Record docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. API operations — all public route handlers introspected
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
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


async def docs_record_client(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Record docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Assemble ComposedDocsResponse with API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 2: Assemble response ----------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.v5.record.export import export_record
    from app.routes.v5.record.get import get_record
    from app.routes.v5.record.search import search_record

    return ComposedDocsResponse(
        name="record",
        type="analytics",
        description=(
            "Record analytics provides per-profile performance dashboards "
            "with attempt history, scoring trends, and progress tracking."
        ),
        entries=[],
        resources=[],
        permissions=[],
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
                export_record,
                description="POST /export — Export record data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
