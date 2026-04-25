"""Model page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the model page:
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
from app.tools.artifacts.model.docs import get_model_docs
from app.tools.artifacts.model.get import get_models as get_model_artifacts

# Entry tool docs
from app.tools.entries.model_drafts.docs import get_model_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.modalities.docs import get_modalities_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.pricing.docs import get_pricing_docs
from app.tools.resources.providers.docs import get_providers_docs
from app.tools.resources.qualities.docs import get_qualities_docs
from app.tools.resources.reasoning_levels.docs import (
    get_reasoning_levels_docs,
)
from app.tools.resources.temperature_levels.docs import (
    get_temperature_levels_docs,
)
from app.tools.resources.values.docs import get_values_docs
from app.tools.resources.voices.docs import get_voices_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Models",
    list_description="Manage AI model configurations.",
    detail_title="— Model",
    detail_description="View and edit model configuration and linked resources.",
    new_title="New Model",
    new_description="Create a new model.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a model by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_model_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Model page context.

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

    async def _get_model_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_docs(conn)

    async def _get_model_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_model_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_departments_docs() -> object:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_modalities_docs() -> object:
        async with pool.acquire() as conn:
            return await get_modalities_docs(conn)

    async def _get_pricing_docs() -> object:
        async with pool.acquire() as conn:
            return await get_pricing_docs(conn)

    async def _get_providers_docs() -> object:
        async with pool.acquire() as conn:
            return await get_providers_docs(conn)

    async def _get_qualities_docs() -> object:
        async with pool.acquire() as conn:
            return await get_qualities_docs(conn)

    async def _get_reasoning_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_reasoning_levels_docs(conn)

    async def _get_temperature_levels_docs() -> object:
        async with pool.acquire() as conn:
            return await get_temperature_levels_docs(conn)

    async def _get_values_docs() -> object:
        async with pool.acquire() as conn:
            return await get_values_docs(conn)

    async def _get_voices_docs() -> object:
        async with pool.acquire() as conn:
            return await get_voices_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.model.permissions_context import (
            resolve_model_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_model_permissions_context(conn, entity_id)

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
        flags,
        modalities,
        pricing,
        providers,
        qualities,
        reasoning_levels,
        temperature_levels,
        values,
        voices,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_model_docs(),
        _get_model_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_flags_docs(),
        _get_modalities_docs(),
        _get_pricing_docs(),
        _get_providers_docs(),
        _get_qualities_docs(),
        _get_reasoning_levels_docs(),
        _get_temperature_levels_docs(),
        _get_values_docs(),
        _get_voices_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.model.permissions import (
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
            entity_perms.active_agent_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_agent_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_agent_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Create a model", content="Create a new AI model configuration with optimized parameters."),
            StarterPrompt(title="From use case", content="I have a specific use case — help me configure the right model for it."),
            StarterPrompt(title="Template-based", content="Create a model configuration from a common pattern like conversational, analytical, or creative."),
        ],
        "search": [
            StarterPrompt(title="Find models", content="Help me find models that match specific capability or performance criteria."),
            StarterPrompt(title="Compare models", content="Compare my model configurations and suggest the best one for each use case."),
            StarterPrompt(title="Audit models", content="Review all models and flag any with suboptimal or inconsistent parameters."),
        ],
        "update": [
            StarterPrompt(title="Enhance model", content="Improve this model's configuration and parameter settings."),
            StarterPrompt(title="Optimize parameters", content="Fine-tune this model's temperature, token limits, and other parameters."),
            StarterPrompt(title="Add capabilities", content="Configure additional modalities, providers, and quality settings for this model."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & tune", content="Duplicate this model and tune the parameters for a different use case."),
            StarterPrompt(title="Bulk clone", content="Create variations of this model with different temperature and reasoning settings."),
        ],
        "draft": [
            StarterPrompt(title="Draft model", content="Start drafting a new model — suggest a provider, parameters, and quality tier."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest parameter improvements before saving."),
        ],
        "export": [
            StarterPrompt(title="Export summary", content="Generate a summary of all model configurations for review."),
            StarterPrompt(title="Export comparison", content="Create a comparison report of model capabilities, pricing, and parameters."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.model.create import create_model
    from app.routes.model.delete import delete_model
    from app.routes.model.draft import patch_model_draft
    from app.routes.model.duplicate import duplicate_model
    from app.routes.model.export import export_models
    from app.routes.model.get import get_model
    from app.routes.model.search import search_model
    from app.routes.model.update import update_model

    return ComposedContextResponse(
        name="model",
        type="artifact",
        description=(
            "Models define AI model configurations. "
            "Each model links to resources (names, descriptions, departments, "
            "flags, modalities, pricing, providers, qualities, reasoning_levels, "
            "temperature_levels, values, voices) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            flags,
            modalities,
            pricing,
            providers,
            qualities,
            reasoning_levels,
            temperature_levels,
            values,
            voices,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the model.",
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
                get_model,
                description="POST /get — Get a single model by ID with hydrated resources.",
            ),
            get_operation_info(
                search_model,
                description="POST /search — Paginated model search with filters.",
            ),
            get_operation_info(
                create_model,
                description="POST /create — Create a new model artifact.",
            ),
            get_operation_info(
                update_model,
                description="POST /update — Update an existing model's resource links.",
            ),
            get_operation_info(
                duplicate_model,
                description="POST /duplicate — Duplicate an existing model.",
            ),
            get_operation_info(
                delete_model,
                description="POST /delete — Delete a model.",
            ),
            get_operation_info(
                patch_model_draft,
                description="PATCH /draft — Create or patch a model draft (autosave).",
            ),
            get_operation_info(
                export_models,
                description="POST /export — Export models as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
