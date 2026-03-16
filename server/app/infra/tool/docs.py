"""Tool docs logic — composable infra architecture.

Composes existing black-box tool docs:
  1. resolve_profile_identity_context — profile (role, departments)
  2. Artifact tool docs — tool_artifact table + CRUD operations
  3. Entry tool docs — tool_drafts MV, tables, operations
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
from app.tools.artifacts.tool.docs import get_tool_docs
from app.tools.artifacts.tool.get import get_tools as get_tool_artifacts

# Entry tool docs
from app.tools.entries.tool_drafts.docs import get_tool_drafts_docs

# Resource tool docs
from app.tools.resources.arg_positions.docs import get_arg_positions_docs
from app.tools.resources.args.docs import get_args_docs
from app.tools.resources.args_outputs.docs import get_args_outputs_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.names.docs import get_names_docs
from app.tools.resources.names.get import get_names

_PAGE_METADATA = PageMetadataConfig(
    list_title="Tools",
    list_description="Manage function calling configurations for agents.",
    detail_title="— Tool",
    detail_description="View and edit tool configuration and linked resources.",
    new_title="New Tool",
    new_description="Create a new function calling tool.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a tool by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_tool_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
        return names_data[0].name if names_data else None


async def docs_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedDocsResponse:
    """Tool docs using composable infra functions.

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

    async def _get_tool_docs() -> object:
        async with pool.acquire() as conn:
            return await get_tool_docs(conn)

    async def _get_tool_drafts_docs() -> object:
        async with pool.acquire() as conn:
            return await get_tool_drafts_docs(conn)

    async def _get_names_docs() -> object:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> object:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_args_docs() -> object:
        async with pool.acquire() as conn:
            return await get_args_docs(conn)

    async def _get_arg_positions_docs() -> object:
        async with pool.acquire() as conn:
            return await get_arg_positions_docs(conn)

    async def _get_args_outputs_docs() -> object:
        async with pool.acquire() as conn:
            return await get_args_outputs_docs(conn)

    (
        artifact,
        drafts,
        names,
        descriptions,
        flags,
        args,
        arg_positions,
        args_outputs,
    ) = await asyncio.gather(
        _get_tool_docs(),
        _get_tool_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_args_docs(),
        _get_arg_positions_docs(),
        _get_args_outputs_docs(),
    )

    # -- Step 3: Page metadata ---------------------------------------------------

    entity_name = None
    if entity_id is not None:
        entity_name = await _resolve_entity_name(pool, redis, entity_id)

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Assemble response ---------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.infra.tool.permissions import (
        compute_can_create,
        compute_can_delete,
        compute_can_draft,
        compute_can_duplicate,
        compute_can_edit,
        has_access,
    )
    from app.routes.v5.tool.create import create_tool
    from app.routes.v5.tool.delete import delete_tool
    from app.routes.v5.tool.draft import patch_tool_draft
    from app.routes.v5.tool.duplicate import duplicate_tool
    from app.routes.v5.tool.export import export_tools
    from app.routes.v5.tool.get import get_tool
    from app.routes.v5.tool.search import search_tool
    from app.routes.v5.tool.update import update_tool

    return ComposedDocsResponse(
        name="tool",
        type="artifact",
        description=(
            "Tools define function calling configurations for agents. "
            "Each tool links to resources (names, descriptions, flags, args, "
            "arg_positions, args_outputs) via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            flags,
            args,
            arg_positions,
            args_outputs,
        ],
        permissions=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the tool.",
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
                get_tool,
                description="POST /get — Get a single tool by ID with hydrated resources.",
            ),
            get_operation_info(
                search_tool,
                description="POST /search — Paginated tool search with filters.",
            ),
            get_operation_info(
                create_tool,
                description="POST /create — Create a new tool artifact.",
            ),
            get_operation_info(
                update_tool,
                description="POST /update — Update an existing tool's resource links.",
            ),
            get_operation_info(
                duplicate_tool,
                description="POST /duplicate — Duplicate an existing tool.",
            ),
            get_operation_info(
                delete_tool,
                description="POST /delete — Delete a tool.",
            ),
            get_operation_info(
                patch_tool_draft,
                description="PATCH /draft — Create or patch a tool draft (autosave).",
            ),
            get_operation_info(
                export_tools,
                description="POST /export — Export tools as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
    )
