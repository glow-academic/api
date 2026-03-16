"""Scenario docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — scenario_artifact table + CRUD operations
  3. Entry tool docs — scenario_drafts MV, tables, operations
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
from app.tools.artifacts.scenario.docs import get_scenario_docs
from app.tools.artifacts.scenario.get import (
    get_scenarios as get_scenario_artifacts,
)

# Entry tool docs
from app.tools.entries.scenario_drafts.docs import get_scenario_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.documents.docs import get_documents_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.images.docs import get_images_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names
from app.tools.resources.objectives.docs import get_objectives_docs
from app.tools.resources.options.docs import get_options_docs
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)
from app.tools.resources.parameters.docs import get_parameters_docs
from app.tools.resources.personas.docs import get_personas_docs
from app.tools.resources.problem_statements.docs import (
    get_problem_statements_docs,
)
from app.tools.resources.questions.docs import get_questions_docs
from app.tools.resources.videos.docs import get_videos_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Scenarios",
    list_description="Manage simulation content and configuration.",
    detail_title="— Scenario",
    detail_description="View and edit scenario configuration and linked resources.",
    new_title="New Scenario",
    new_description="Create a new scenario configuration.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a scenario by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_scenario_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def docs_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Scenario docs using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> profile check
      2. Parallel: artifact docs + entry docs + all resource docs
      3. Assemble ComposedDocsResponse with permissions + API operations
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context -----------------------------------------------

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Parallel docs fetches -----------------------------------------

    async def _get_scenario_docs() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_docs(conn)

    async def _get_scenario_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_scenario_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_documents_docs() -> object:
        async with pool.acquire() as conn:
            return await get_documents_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_images_docs() -> object:
        async with pool.acquire() as conn:
            return await get_images_docs(conn)

    async def _get_objectives_docs() -> object:
        async with pool.acquire() as conn:
            return await get_objectives_docs(conn)

    async def _get_options_docs() -> object:
        async with pool.acquire() as conn:
            return await get_options_docs(conn)

    async def _get_parameter_fields_docs() -> object:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    async def _get_parameters_docs() -> object:
        async with pool.acquire() as conn:
            return await get_parameters_docs(conn)

    async def _get_personas_docs() -> object:
        async with pool.acquire() as conn:
            return await get_personas_docs(conn)

    async def _get_problem_statements_docs() -> object:
        async with pool.acquire() as conn:
            return await get_problem_statements_docs(conn)

    async def _get_questions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_questions_docs(conn)

    async def _get_videos_docs() -> object:
        async with pool.acquire() as conn:
            return await get_videos_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        departments,
        documents,
        flags,
        images,
        objectives,
        options,
        parameter_fields,
        parameters,
        personas,
        problem_statements,
        questions,
        videos,
    ) = await asyncio.gather(
        _get_scenario_docs(),
        _get_scenario_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_documents_docs(),
        _get_flags_docs(),
        _get_images_docs(),
        _get_objectives_docs(),
        _get_options_docs(),
        _get_parameter_fields_docs(),
        _get_parameters_docs(),
        _get_personas_docs(),
        _get_problem_statements_docs(),
        _get_questions_docs(),
        _get_videos_docs(),
    )

    # -- Step 3: Page metadata ---------------------------------------------------

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.scenario.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.scenario.create import create_scenario
    from app.routes.v5.scenario.delete import delete_scenario
    from app.routes.v5.scenario.draft import patch_scenario_draft
    from app.routes.v5.scenario.duplicate import duplicate_scenario
    from app.routes.v5.scenario.export import export_scenarios
    from app.routes.v5.scenario.get import get_scenario
    from app.routes.v5.scenario.search import search_scenario
    from app.routes.v5.scenario.update import update_scenario

    return ComposedDocsResponse(
        name="scenario",
        type="artifact",
        description=(
            "Scenarios define simulation content and configuration. "
            "Each scenario links to resources (names, descriptions, departments, "
            "documents, flags, images, objectives, options, parameter_fields, "
            "parameters, personas, problem_statements, questions, videos) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            documents,
            flags,
            images,
            objectives,
            options,
            parameter_fields,
            parameters,
            personas,
            problem_statements,
            questions,
            videos,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the scenario.",
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
                get_scenario,
                description="POST /get — Get a single scenario by ID with hydrated resources.",
            ),
            get_operation_info(
                search_scenario,
                description="POST /search — Paginated scenario search with filters.",
            ),
            get_operation_info(
                create_scenario,
                description="POST /create — Create a new scenario artifact.",
            ),
            get_operation_info(
                update_scenario,
                description="POST /update — Update an existing scenario's resource links.",
            ),
            get_operation_info(
                duplicate_scenario,
                description="POST /duplicate — Duplicate an existing scenario.",
            ),
            get_operation_info(
                delete_scenario,
                description="POST /delete — Delete a scenario.",
            ),
            get_operation_info(
                patch_scenario_draft,
                description="PATCH /draft — Create or patch a scenario draft (autosave).",
            ),
            get_operation_info(
                export_scenarios,
                description="POST /export — Export scenarios as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
