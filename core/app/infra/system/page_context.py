"""System page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the system page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Entry docs — schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Page metadata — titles and descriptions for list/detail/new views
"""

from __future__ import annotations

from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.build_profile_summary import build_profile_summary
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

ARTIFACT_TYPE = "system"

_PAGE_METADATA = PageMetadataConfig(
    list_title="System",
    list_description="System operational analytics and monitoring.",
    detail_title="System",
    detail_description="System operational detail view.",
    new_title="System",
    new_description="System operational analytics.",
)


async def page_context_system_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """system page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("system/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "system", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_system_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_system_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """System page context.

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

    # System is analytics — no create/draft/duplicate semantics.
    caller_permissions = CallerPermissions(
        can_create=False,
        can_draft=False,
        can_duplicate=False,
    )

    # -- Step 4: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 5: Starter prompts ------------------------------------------------

    prompts = OperationPrompts(prompts={
        "get": [
            StarterPrompt(title="Review system status", content="Review system status"),
            StarterPrompt(title="Analyze system health", content="Analyze system health"),
        ],
        "export": [
            StarterPrompt(title="Export system data", content="Export system data"),
        ],
    })

    # -- Step 6: Assemble response ----------------------------------------------

    return ComposedContextResponse(
        name="system",
        type="analytics",
        description=(
            "System analytics provides operational views including health "
            "monitoring, activity tracking, session management, pricing, "
            "and group details."
        ),
        artifact=None,
        entries=([] if schema else None),
        resources=([] if schema else None),
        permission_docs=([] if schema else None),
        api_operations=([] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
