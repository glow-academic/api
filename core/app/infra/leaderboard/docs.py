"""Leaderboard docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Permission functions — introspected via get_operation_info
  3. API operations — all public route handlers introspected
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
    list_title="Leaderboard",
    list_description="View performance rankings and accolades.",
    detail_title="Leaderboard",
    detail_description="View leaderboard rankings and comparative metrics.",
    new_title="Leaderboard",
    new_description="View leaderboard rankings and comparative metrics.",
)


async def docs_leaderboard_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Leaderboard docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → profile check
      2. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Page metadata ───────────────────────────────────────────────────
    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # ── Step 2: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.leaderboard.permissions import (
        build_leaderboard_rows,
        build_leaderboard_sections,
        compute_accolade_winners,
        compute_message_stats,
    )
    from app.routes.v5.leaderboard.export import export_leaderboard
    from app.routes.v5.leaderboard.get import get_leaderboard
    from app.routes.v5.leaderboard.refresh import leaderboard_refresh
    from app.routes.v5.leaderboard.search import search_leaderboard

    return ComposedDocsResponse(
        name="leaderboard",
        type="analytics",
        description=(
            "Leaderboard analytics ranks user performance with accolades, "
            "comparative metrics, and historical tracking across simulations."
        ),
        entries=[],
        resources=[],
        permissions=[
            get_operation_info(
                build_leaderboard_rows,
                description="Build ranked leaderboard data rows from MV slices.",
            ),
            get_operation_info(
                compute_accolade_winners,
                description="Compute accolade winners from leaderboard data rows.",
            ),
            get_operation_info(
                build_leaderboard_sections,
                description="Build leaderboard sections with status and metrics.",
            ),
            get_operation_info(
                compute_message_stats,
                description="Compute message-level statistics for leaderboard entries.",
            ),
        ],
        api_operations=[
            get_operation_info(
                get_leaderboard,
                description="POST /get — Get leaderboard rankings and accolades.",
            ),
            get_operation_info(
                search_leaderboard,
                description="POST /search — Search leaderboard history entries.",
            ),
            get_operation_info(
                leaderboard_refresh,
                description="POST /refresh — Refresh leaderboard materialized views.",
            ),
            get_operation_info(
                export_leaderboard,
                description="POST /export — Export leaderboard data as CSV/ZIP.",
            ),
        ],
        page_metadata=page_metadata,
    )
