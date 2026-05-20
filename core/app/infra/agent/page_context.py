"""Agent page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the agent page:
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
from app.tools.artifacts.agent.docs import get_agent_docs
from app.tools.artifacts.agent.get import get_agents as get_agent_artifacts

# Entry tool docs
from app.tools.entries.agent_drafts.docs import get_agent_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.instructions.docs import get_instructions_docs
from app.tools.resources.models.docs import get_models_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.prompts.docs import get_prompts_docs
from app.tools.resources.qualities.docs import get_qualities_docs
from app.tools.resources.reasoning_levels.docs import (
    get_reasoning_levels_docs,
)
from app.tools.resources.rubrics.docs import get_rubrics_docs
from app.tools.resources.temperature_levels.docs import (
    get_temperature_levels_docs,
)
from app.tools.resources.tools.docs import get_tools_docs
from app.tools.resources.voices.docs import get_voices_docs
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

_PAGE_METADATA = PageMetadataConfig(
    list_title="Agents",
    list_description="Manage AI assistant configurations.",
    detail_title="— Agent",
    detail_description="View and edit agent configuration and linked resources.",
    new_title="New Agent",
    new_description="Create a new agent.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for an agent by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_agent_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """agent page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("agent/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
            "schema": schema,
        }),
        tags=["context", "agent", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_agent_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
            schema=schema,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_agent_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    schema: bool = False,
) -> ComposedContextResponse:
    """Agent page context.

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

    async def _get_agent_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_agent_docs(conn)

    async def _get_agent_drafts_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_agent_drafts_docs(conn)

    async def _get_names_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_models_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_models_docs(conn)

    async def _get_prompts_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_prompts_docs(conn)

    async def _get_instructions_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_instructions_docs(conn)

    async def _get_flags_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_tools_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_tools_docs(conn)

    async def _get_qualities_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_qualities_docs(conn)

    async def _get_reasoning_levels_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_reasoning_levels_docs(conn)

    async def _get_temperature_levels_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_temperature_levels_docs(conn)

    async def _get_rubrics_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_rubrics_docs(conn)

    async def _get_voices_docs() -> object:
        if not schema:
            return None  # type: ignore[return-value]
        async with pool.acquire() as conn:
            return await get_voices_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.agent.permissions_context import (
            resolve_agent_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_agent_permissions_context(conn, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

    (
        artifact,
        drafts,
        names,
        descriptions,
        models,
        prompts,
        instructions,
        flags,
        departments,
        tools,
        qualities,
        reasoning_levels,
        temperature_levels,
        rubrics,
        voices,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_agent_docs(),
        _get_agent_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_models_docs(),
        _get_prompts_docs(),
        _get_instructions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_tools_docs(),
        _get_qualities_docs(),
        _get_reasoning_levels_docs(),
        _get_temperature_levels_docs(),
        _get_rubrics_docs(),
        _get_voices_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.agent.permissions import (
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
        has_agent_access = has_access(
            profile.role_level,
            profile.department_ids,
            entity_perms.department_ids,
        )
        caller_permissions.has_access = has_agent_access
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            has_agent_access,
            [],  # missing_tools — not available in context
            entity_id,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            0,  # active_settings_count — optimistic (same as search)
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            has_agent_access,
            [],  # missing_tools — not available in context
            entity_id,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create an agent", content="Create a new AI agent with specific capabilities, personality, and response style."),
            StarterPrompt(title="From description", content="I have an agent concept in mind — help me build a complete agent configuration."),
            StarterPrompt(title="Template-based", content="Create an agent from a common template like tutor, interviewer, or coach."),
        ],
        "search": [
            StarterPrompt(title="Find agents", content="Help me find agents that match specific capabilities or training scenarios."),
            StarterPrompt(title="Compare agents", content="Compare my agents and identify which is best suited for each use case."),
            StarterPrompt(title="Audit agents", content="Review all agents and flag any with incomplete or inconsistent configurations."),
        ],
        "update": [
            StarterPrompt(title="Enhance agent", content="Improve this agent's configuration, capabilities, and response patterns."),
            StarterPrompt(title="Refine behavior", content="Make this agent's behavior more consistent and aligned with its intended purpose."),
            StarterPrompt(title="Add tools", content="Add missing tool configurations, instructions, and model settings to this agent."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & vary", content="Duplicate this agent and create a variation with different capabilities or style."),
            StarterPrompt(title="Bulk clone", content="Create 3 variations of this agent tuned for different training scenarios."),
        ],
        "draft": [
            StarterPrompt(title="Draft agent", content="Start drafting a new agent — suggest a name, role, and key capabilities."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export summary", content="Generate a summary of all agents suitable for sharing with stakeholders."),
            StarterPrompt(title="Export comparison", content="Create a comparison report of agent configurations and capabilities."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.agent.create import create_agent
    from app.routes.agent.delete import delete_agent
    from app.routes.agent.draft import patch_agent_draft
    from app.routes.agent.duplicate import duplicate_agent
    from app.routes.agent.export import export_agents
    from app.routes.agent.get import get_agent
    from app.routes.agent.search import search_agent
    from app.routes.agent.update import update_agent

    return ComposedContextResponse(
        name="agent",
        type="artifact",
        description=(
            "Agents define AI assistant configurations. "
            "Each agent links to resources (names, descriptions, models, prompts, "
            "instructions, departments, flags, tools, qualities, reasoning_levels, "
            "temperature_levels, rubrics, voices) via junction tables."
        ),
        artifact=(artifact if schema else None),
        entries=([drafts] if schema else None),
        resources=([
            names,
            descriptions,
            models,
            instructions,
            flags,
            departments,
            tools,
            qualities,
            reasoning_levels,
            temperature_levels,
            rubrics,
            voices,
        ] if schema else None),
        permission_docs=([
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the agent.",
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
                get_agent,
                description="POST /get — Get a single agent by ID with hydrated resources.",
            ),
            get_operation_info(
                search_agent,
                description="POST /search — Paginated agent search with filters.",
            ),
            get_operation_info(
                create_agent,
                description="POST /create — Create a new agent artifact.",
            ),
            get_operation_info(
                update_agent,
                description="POST /update — Update an existing agent's resource links.",
            ),
            get_operation_info(
                duplicate_agent,
                description="POST /duplicate — Duplicate an existing agent.",
            ),
            get_operation_info(
                delete_agent,
                description="POST /delete — Delete an agent.",
            ),
            get_operation_info(
                patch_agent_draft,
                description="PATCH /draft — Create or patch an agent draft (autosave).",
            ),
            get_operation_info(
                export_agents,
                description="POST /export — Export agents as denormalized CSV.",
            ),
        ] if schema else None),
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
