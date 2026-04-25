"""Scenario page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the scenario page:
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

from app.infra.docs.get_operation_info import get_operation_info
from app.infra.docs.types import (
    CallerPermissions,
    ComposedContextResponse,
    OperationPrompts,
    StarterPrompt,
)
from app.infra.docs.build_profile_summary import build_profile_summary
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
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Scenario page context.

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

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.scenario.permissions_context import (
            resolve_scenario_permissions_context,
        )
        return await resolve_scenario_permissions_context(pool, entity_id)

    async def _get_entity_name() -> str | None:
        if not entity_id:
            return None
        return await _resolve_entity_name(pool, redis, entity_id)

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
        entity_perms,
        entity_name,
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
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.scenario.permissions import (
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
            profile.department_ids,
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
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Design a scenario", content="Create a new practice scenario with objectives, personas, and evaluation criteria."),
            StarterPrompt(title="From topic", content="I have a training topic — help me design a complete practice scenario for it."),
            StarterPrompt(title="Template-based", content="Create a scenario from a common template like interview, negotiation, or customer service."),
        ],
        "search": [
            StarterPrompt(title="Find scenarios", content="Help me find scenarios that match specific training objectives or skill areas."),
            StarterPrompt(title="Compare scenarios", content="Compare my scenarios and identify gaps in training coverage."),
            StarterPrompt(title="Audit scenarios", content="Review all scenarios and flag any with missing objectives or incomplete configurations."),
        ],
        "update": [
            StarterPrompt(title="Enhance scenario", content="Improve this scenario's objectives, problem statement, and evaluation flow."),
            StarterPrompt(title="Add resources", content="Add missing personas, documents, and evaluation criteria to this scenario."),
            StarterPrompt(title="Adjust difficulty", content="Tune this scenario's difficulty level and learner progression."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & vary", content="Duplicate this scenario and create a variation with different difficulty or context."),
            StarterPrompt(title="Bulk clone", content="Create multiple variations of this scenario for different training objectives."),
        ],
        "draft": [
            StarterPrompt(title="Draft scenario", content="Start drafting a new scenario — suggest objectives, personas, and a problem statement."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export summary", content="Generate a summary of all scenarios suitable for curriculum review."),
            StarterPrompt(title="Export analysis", content="Analyze my scenarios and create a report on training coverage and quality."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.scenario.create import create_scenario
    from app.routes.scenario.delete import delete_scenario
    from app.routes.scenario.draft import patch_scenario_draft
    from app.routes.scenario.duplicate import duplicate_scenario
    from app.routes.scenario.export import export_scenarios
    from app.routes.scenario.get import get_scenario
    from app.routes.scenario.search import search_scenario
    from app.routes.scenario.update import update_scenario

    return ComposedContextResponse(
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
        permission_docs=[
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
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
