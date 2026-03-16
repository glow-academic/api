"""Agent docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — agent_artifact table + CRUD operations
  3. Entry tool docs — agent_drafts MV, tables, operations
  4. Resource tool docs — all linked resources (names, descriptions, etc.)
  5. Permission functions — introspected via get_operation_info
  6. API operations — all public route handlers introspected
"""

from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import ComposedDocsResponse
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
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Agent docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → profile check
      2. Parallel: artifact docs + entry docs + all resource docs
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Parallel docs fetches ──────────────────────────────────

    async def _get_agent_docs() -> object:
        async with pool.acquire() as conn:
            return await get_agent_docs(conn)

    async def _get_agent_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_agent_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_models_docs() -> object:
        async with pool.acquire() as conn:
            return await get_models_docs(conn)

    async def _get_prompts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_prompts_docs(conn)

    async def _get_instructions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_instructions_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_tools_docs() -> object:
        async with pool.acquire() as conn:
            return await get_tools_docs(conn)

    async def _get_qualities_docs() -> object:
        async with pool.acquire() as conn:
            return await get_qualities_docs(conn)

    async def _get_reasoning_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_reasoning_levels_docs(conn)

    async def _get_temperature_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_temperature_levels_docs(conn)

    async def _get_rubrics_docs() -> object:
        async with pool.acquire() as conn:
            return await get_rubrics_docs(conn)

    async def _get_voices_docs() -> object:
        async with pool.acquire() as conn:
            return await get_voices_docs(conn)

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
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────
    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)
    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.agent.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.agent.create import create_agent
    from app.routes.v5.agent.delete import delete_agent
    from app.routes.v5.agent.draft import patch_agent_draft
    from app.routes.v5.agent.duplicate import duplicate_agent
    from app.routes.v5.agent.export import export_agents
    from app.routes.v5.agent.get import get_agent
    from app.routes.v5.agent.search import search_agent
    from app.routes.v5.agent.update import update_agent

    return ComposedDocsResponse(
        name="agent",
        type="artifact",
        description=(
            "Agents define AI assistant configurations. "
            "Each agent links to resources (names, descriptions, models, prompts, "
            "instructions, departments, flags, tools, qualities, reasoning_levels, "
            "temperature_levels, rubrics, voices) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
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
        ],
        permissions=[
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
        ],
        api_operations=[
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
        ],
        page_metadata=page_metadata,
    )
