"""Persona docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — persona_artifact table + CRUD operations
  3. Entry tool docs — persona_drafts MV, tables, operations
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
from app.tools.artifacts.persona.docs import get_persona_docs
from app.tools.artifacts.persona.get import (
    get_personas as get_persona_artifacts,
)

# Entry tool docs
from app.tools.entries.persona_drafts.docs import get_persona_drafts_docs

# Resource tool docs
from app.tools.resources.colors.docs import get_colors_docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.examples.docs import get_examples_docs
from app.tools.resources.fields.docs import get_fields_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.icons.docs import get_icons_docs
from app.tools.resources.instructions.docs import get_instructions_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)
from app.tools.resources.parameters.docs import get_parameters_docs
from app.tools.resources.voices.docs import get_voices_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Personas",
    list_description="Manage character profiles used in scenarios.",
    detail_title="— Persona",
    detail_description="View and edit persona configuration and linked resources.",
    new_title="New Persona",
    new_description="Create a new persona character profile.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a persona by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_persona_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Persona docs using composable infra functions.

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
    # Each branch acquires its own connection from the pool.

    async def _get_persona_docs() -> list:
        async with pool.acquire() as conn:
            return await get_persona_docs(conn)

    async def _get_persona_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_persona_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_colors_docs() -> list:
        async with pool.acquire() as conn:
            return await get_colors_docs(conn)

    async def _get_icons_docs() -> list:
        async with pool.acquire() as conn:
            return await get_icons_docs(conn)

    async def _get_instructions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_instructions_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_examples_docs() -> list:
        async with pool.acquire() as conn:
            return await get_examples_docs(conn)

    async def _get_parameter_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    async def _get_parameters_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameters_docs(conn)

    async def _get_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_fields_docs(conn)

    async def _get_voices_docs() -> list:
        async with pool.acquire() as conn:
            return await get_voices_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        colors,
        icons,
        instructions,
        flags,
        departments,
        examples,
        parameter_fields,
        parameters,
        fields,
        voices,
    ) = await asyncio.gather(
        _get_persona_docs(),
        _get_persona_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_colors_docs(),
        _get_icons_docs(),
        _get_instructions_docs(),
        _get_flags_docs(),
        _get_departments_docs(),
        _get_examples_docs(),
        _get_parameter_fields_docs(),
        _get_parameters_docs(),
        _get_fields_docs(),
        _get_voices_docs(),
    )

    # ── Step 3: Page metadata ───────────────────────────────────────────

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # ── Step 4: Assemble response ──────────────────────────────────────

    # Lazy imports to avoid circular dependencies
    from app.infra.persona.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.persona.create import create_persona
    from app.routes.v5.persona.delete import delete_persona
    from app.routes.v5.persona.draft import patch_persona_draft
    from app.routes.v5.persona.duplicate import duplicate_persona
    from app.routes.v5.persona.export import export_personas
    from app.routes.v5.persona.get import get_persona
    from app.routes.v5.persona.search import search_persona
    from app.routes.v5.persona.update import update_persona

    return ComposedDocsResponse(
        name="persona",
        type="artifact",
        description=(
            "Personas define character profiles used in scenarios. "
            "Each persona links to resources (names, descriptions, colors, icons, "
            "instructions, departments, examples, flags, parameter_fields, voices) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            colors,
            icons,
            instructions,
            flags,
            departments,
            examples,
            parameter_fields,
            parameters,
            fields,
            voices,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the persona.",
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
                get_persona,
                description="POST /get — Get a single persona by ID with hydrated resources.",
            ),
            get_operation_info(
                search_persona,
                description="POST /search — Paginated persona search with filters.",
            ),
            get_operation_info(
                create_persona,
                description="POST /create — Create a new persona artifact.",
            ),
            get_operation_info(
                update_persona,
                description="POST /update — Update an existing persona's resource links.",
            ),
            get_operation_info(
                duplicate_persona,
                description="POST /duplicate — Duplicate an existing persona.",
            ),
            get_operation_info(
                delete_persona,
                description="POST /delete — Delete a persona.",
            ),
            get_operation_info(
                patch_persona_draft,
                description="PATCH /draft — Create or patch a persona draft (autosave).",
            ),
            get_operation_info(
                export_personas,
                description="POST /export — Export personas as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
