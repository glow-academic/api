"""Rubric page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the rubric page:
  1. resolve_profile_identity_context — who you are (name, role, departments)
  2. Artifact/entry/resource docs — schema introspection (same as docs.py)
  3. Permission evaluation — concrete booleans for THIS caller
  4. Entity permissions — can_edit/can_delete when entity_id is provided
  5. Page metadata — titles and descriptions for list/detail/new views
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
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Artifact tool docs
from app.tools.artifacts.rubric.docs import get_rubric_docs
from app.tools.artifacts.rubric.get import (
    get_rubrics as get_rubric_artifacts,
)

# Entry tool docs
from app.tools.entries.rubric_drafts.docs import get_rubric_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.points.docs import get_points_docs
from app.tools.resources.standard_groups.docs import (
    get_standard_groups_docs,
)
from app.tools.resources.standards.docs import get_standards_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Rubrics",
    list_description="Manage evaluation criteria with scoring standards.",
    detail_title="— Rubric",
    detail_description="View and edit rubric configuration and linked resources.",
    new_title="New Rubric",
    new_description="Create a new evaluation rubric.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a rubric by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_rubric_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """rubric page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("rubric/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "rubric", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_rubric_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_rubric_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Rubric page context.

    Flow:
      1. resolve_profile_identity_context -> profile identity (kept, not discarded)
      2. Parallel: artifact docs + entry docs + all resource docs
         + entity permissions context (if entity_id)
         + entity name (if entity_id)
      3. Evaluate caller permissions using profile data
      4. Assemble ComposedContextResponse
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context ------------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches + entity resolution ----------------------
    # Each branch acquires its own connection from the pool.

    async def _get_rubric_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_rubric_docs(conn)

    async def _get_rubric_drafts_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_rubric_drafts_docs(conn)

    async def _get_names_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_points_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_points_docs(conn)

    async def _get_standard_groups_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_standard_groups_docs(conn)

    async def _get_standards_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_standards_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.rubric.permissions_context import (
            resolve_rubric_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_rubric_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        departments,
        points,
        standard_groups,
        standards,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_rubric_docs(),
        _get_rubric_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_points_docs(),
        _get_standard_groups_docs(),
        _get_standards_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.rubric.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        compute_disabled_reason,
        has_access,
    )

    caller_permissions = CallerPermissions(
        can_create=compute_can_create(
            profile.role_level,
            profile.role_permissions,
            profile.department_ids,
        ),
        can_draft=compute_can_draft(
            profile.role_level,
            profile.role_permissions,
        ),
        can_duplicate=compute_can_duplicate(
            profile.role_level,
            profile.role_permissions,
        ),
    )

    # Entity-level permissions (only when entity_id was provided and found)
    if entity_id and entity_perms and entity_perms.exists:
        caller_permissions.has_access = has_access(
            profile.role_level,
            profile.department_ids,
            entity_perms.department_ids,
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_simulation_count,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_simulation_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_simulation_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Build a rubric", content="Create a new rubric with clear criteria, point values, and performance levels."),
            StarterPrompt(title="From objectives", content="I have learning objectives — help me create a rubric to assess them."),
            StarterPrompt(title="Template-based", content="Create a rubric from a common template like holistic, analytic, or single-point."),
        ],
        "search": [
            StarterPrompt(title="Find rubrics", content="Help me find rubrics that match specific assessment areas or scoring approaches."),
            StarterPrompt(title="Compare rubrics", content="Compare my rubrics and identify overlapping criteria or scoring inconsistencies."),
            StarterPrompt(title="Audit rubrics", content="Review all rubrics and flag any with vague criteria or unbalanced point distributions."),
        ],
        "update": [
            StarterPrompt(title="Refine criteria", content="Improve this rubric's criteria descriptions and performance level descriptors."),
            StarterPrompt(title="Adjust scoring", content="Rebalance this rubric's point distribution to better reflect learning priorities."),
            StarterPrompt(title="Add standards", content="Add missing evaluation standards and scoring levels to this rubric."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & adapt", content="Duplicate this rubric and adapt its criteria for a different subject area."),
            StarterPrompt(title="Difficulty variant", content="Create a variation of this rubric with adjusted expectations for a different level."),
        ],
        "draft": [
            StarterPrompt(title="Draft rubric", content="Start drafting a new rubric — suggest criteria, point values, and performance levels."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to scoring before saving."),
        ],
        "export": [
            StarterPrompt(title="Export rubric", content="Generate a printable summary of all rubrics with their criteria and scoring."),
            StarterPrompt(title="Export analysis", content="Analyze my rubrics and create a report on assessment coverage and quality."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.rubric.create import create_rubric
    from app.routes.rubric.delete import delete_rubric
    from app.routes.rubric.draft import patch_rubric_draft
    from app.routes.rubric.duplicate import duplicate_rubric
    from app.routes.rubric.export import export_rubrics
    from app.routes.rubric.get import get_rubric
    from app.routes.rubric.search import search_rubric
    from app.routes.rubric.update import update_rubric

    return ComposedContextResponse(
        name="rubric",
        type="artifact",
        description=(
            "Rubrics define evaluation criteria with scoring standards. "
            "Each rubric links to resources (names, descriptions, departments, "
            "flags, points, standard_groups, standards) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            descriptions,
            flags,
            departments,
            points,
            standard_groups,
            standards,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the rubric.",
            ),
            get_operation_info(
                compute_can_edit,
                description="Unified edit permission for UI and save enforcement.",
            ),
            get_operation_info(
                compute_can_delete,
                description="Delete permission — same as edit + usage check.",
            ),
            get_operation_info(
                compute_can_duplicate,
                description="Duplicate — role-only check.",
            ),
            get_operation_info(
                compute_can_create,
                description="Create new artifact — role + department check.",
            ),
            get_operation_info(
                compute_can_draft,
                description="Draft — role-only check.",
            ),
        ] if schema else None),
        api_operations=([
            get_operation_info(
                get_rubric,
                description="POST /get — Get a single rubric by ID with hydrated resources.",
            ),
            get_operation_info(
                search_rubric,
                description="POST /search — Paginated rubric search with filters.",
            ),
            get_operation_info(
                create_rubric,
                description="POST /create — Create a new rubric artifact.",
            ),
            get_operation_info(
                update_rubric,
                description="POST /update — Update an existing rubric's resource links.",
            ),
            get_operation_info(
                duplicate_rubric,
                description="POST /duplicate — Duplicate an existing rubric.",
            ),
            get_operation_info(
                delete_rubric,
                description="POST /delete — Delete a rubric.",
            ),
            get_operation_info(
                patch_rubric_draft,
                description="PATCH /draft — Create or patch a rubric draft (autosave).",
            ),
            get_operation_info(
                export_rubrics,
                description="POST /export — Export rubrics as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
