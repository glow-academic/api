"""Health page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the health page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — schema introspection (same as docs.py)
  3. Page metadata — titles and descriptions for list/detail/new views
  4. Caller permissions — simple defaults (health has no artifact permissions)
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    DocsResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Entry tool docs
from app.tools.entries.health.docs import get_health_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Health",
    list_description="Monitor system performance and health.",
    detail_title="Health",
    detail_description="View system health metrics and status.",
    new_title="Health",
    new_description="Monitor system performance and health.",
)


async def page_context_health_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """health page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("health/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "health", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_health_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_health_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Health page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: entry docs
      3. Assemble ComposedContextResponse with API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches ------------------------------------------

    async def _fetch_health_docs() -> DocsResponse:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_health_docs(conn)

    (health,) = await asyncio.gather(
        _fetch_health_docs(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA)

    # -- Step 4: Caller permissions (simple defaults — health has no perms) -----

    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="Check status", content="Show current system health metrics and service status indicators."),
            StarterPrompt(title="Find issues", content="Identify any degraded services or health warnings in the system."),
            StarterPrompt(title="Diagnose problem", content="Help diagnose the root cause of a specific health concern."),
        ],
        "export": [
            StarterPrompt(title="Export health", content="Export system health metrics and status data as CSV."),
            StarterPrompt(title="Download report", content="Generate a downloadable system health diagnostics report."),
        ],
        "refresh": [
            StarterPrompt(title="Refresh health", content="Refresh the health materialized views with the latest status data."),
            StarterPrompt(title="Update checks", content="Rebuild health analytics to include the most recent service checks."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.system.health.export import export_health
    from app.routes.system.health import get_health
    from app.routes.system.health.refresh import health_refresh

    return ComposedContextResponse(
        name="health",
        type="analytics",
        description=(
            "Health analytics monitors system performance metrics, "
            "service health indicators, and operational status."
        ),
        entries=([health] if schema else None),
        resources=([] if schema else None),
        permission_docs=([] if schema else None),
        api_operations=([
            get_operation_info(
                get_health,
                description="POST /get — Get system health metrics and status.",
            ),
            get_operation_info(
                health_refresh,
                description="POST /refresh — Refresh health materialized views.",
            ),
            get_operation_info(
                export_health,
                description="POST /export — Export health data as CSV/ZIP.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
