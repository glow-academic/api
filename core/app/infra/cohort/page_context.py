"""Cohort page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the cohort page:
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
from app.infra.server_timing import timed

# Artifact tool docs
from app.tools.artifacts.cohort.docs import get_cohort_docs
from app.tools.artifacts.cohort.get import get_cohorts as get_cohort_artifacts

# Entry tool docs
from app.tools.entries.cohort_drafts.docs import get_cohort_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.personas.docs import get_personas_docs
from app.tools.resources.profile_personas.docs import (
    get_profile_personas_docs,
)
from app.tools.resources.profiles.docs import get_profiles_docs
from app.tools.resources.simulation_availability.docs import (
    get_simulation_availability_docs,
)
from app.tools.resources.simulation_positions.docs import (
    get_simulation_positions_docs,
)
from app.tools.resources.simulations.docs import get_simulations_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Cohorts",
    list_description="Manage groups of profiles assigned to simulations.",
    detail_title="— Cohort",
    detail_description="View and edit cohort configuration and linked resources.",
    new_title="New Cohort",
    new_description="Create a new cohort.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a cohort by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_cohort_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_cohort_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """cohort page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("cohort/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "cohort", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_cohort_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_cohort_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Cohort page context.

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

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches + entity resolution ----------------------
    # Each branch acquires its own connection from the pool.

    async def _get_cohort_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_cohort_docs(conn)

    async def _get_cohort_drafts_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_cohort_drafts_docs(conn)

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

    async def _get_departments_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_personas_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_personas_docs(conn)

    async def _get_profile_personas_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_profile_personas_docs(conn)

    async def _get_profiles_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_profiles_docs(conn)

    async def _get_simulations_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_simulations_docs(conn)

    async def _get_simulation_availability_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_simulation_availability_docs(conn)

    async def _get_simulation_positions_docs() -> list:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_simulation_positions_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.cohort.permissions_context import (
            resolve_cohort_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_cohort_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    with timed("docs"):
     (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        flags,
        personas,
        profile_personas,
        profiles,
        simulations,
        simulation_availability,
        simulation_positions,
        entity_perms,
        entity_name,
     ) = await asyncio.gather(
        _get_cohort_docs(),
        _get_cohort_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_personas_docs(),
        _get_profile_personas_docs(),
        _get_profiles_docs(),
        _get_simulations_docs(),
        _get_simulation_availability_docs(),
        _get_simulation_positions_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.cohort.permissions import (
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
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            0,  # usage_count — cohort deletion not blocked by profile links
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    with timed("profile_summary"):
        profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create a cohort", content="Create a new student cohort with appropriate grouping and scheduling."),
            StarterPrompt(title="From class roster", content="I have a class roster — help me organize it into a well-structured cohort."),
            StarterPrompt(title="Template-based", content="Create a cohort from a common template like course section or training group."),
        ],
        "search": [
            StarterPrompt(title="Find cohorts", content="Help me find cohorts that match specific criteria or scheduling needs."),
            StarterPrompt(title="Compare cohorts", content="Compare my cohorts and identify gaps in student coverage or scheduling."),
            StarterPrompt(title="Audit cohorts", content="Review all cohorts and flag any with missing members or incomplete setups."),
        ],
        "update": [
            StarterPrompt(title="Enhance cohort", content="Improve this cohort's description, scheduling, and member organization."),
            StarterPrompt(title="Optimize grouping", content="Suggest better grouping strategies for this cohort's members."),
            StarterPrompt(title="Add simulations", content="Add simulation assignments and persona mappings to this cohort."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & adjust", content="Duplicate this cohort and adjust it for a different course section or term."),
            StarterPrompt(title="Bulk clone", content="Create variations of this cohort for multiple parallel sections."),
        ],
        "draft": [
            StarterPrompt(title="Draft cohort", content="Start drafting a new cohort — suggest a name, structure, and member criteria."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export roster", content="Generate an export of all cohorts with their member lists and assignments."),
            StarterPrompt(title="Export schedule", content="Create a scheduling overview of cohort simulation assignments."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.cohort.create import create_cohort
    from app.routes.cohort.delete import delete_cohort
    from app.routes.cohort.draft import patch_cohort_draft
    from app.routes.cohort.duplicate import duplicate_cohort
    from app.routes.cohort.export import export_cohorts
    from app.routes.cohort.get import get_cohort
    from app.routes.cohort.search import search_cohort
    from app.routes.cohort.update import update_cohort

    return ComposedContextResponse(
        name="cohort",
        type="artifact",
        description=(
            "Cohorts define groups of profiles assigned to simulations. "
            "Each cohort links to resources (names, descriptions, departments, "
            "flags, personas, profiles, profile_personas, simulations, "
            "simulation_availability, simulation_positions) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            descriptions,
            departments,
            flags,
            personas,
            profile_personas,
            profiles,
            simulations,
            simulation_availability,
            simulation_positions,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the cohort.",
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
                get_cohort,
                description="POST /get — Get a single cohort by ID with hydrated resources.",
            ),
            get_operation_info(
                search_cohort,
                description="POST /search — Paginated cohort search with filters.",
            ),
            get_operation_info(
                create_cohort,
                description="POST /create — Create a new cohort artifact.",
            ),
            get_operation_info(
                update_cohort,
                description="POST /update — Update an existing cohort's resource links.",
            ),
            get_operation_info(
                duplicate_cohort,
                description="POST /duplicate — Duplicate an existing cohort.",
            ),
            get_operation_info(
                delete_cohort,
                description="POST /delete — Delete a cohort.",
            ),
            get_operation_info(
                patch_cohort_draft,
                description="PATCH /draft — Create or patch a cohort draft (autosave).",
            ),
            get_operation_info(
                export_cohorts,
                description="POST /export — Export cohorts as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
