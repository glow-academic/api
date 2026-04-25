"""Tool page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the tool page:
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

# Name hydration
from app.tools.resources.names.get import get_names

from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)

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
    names_data = await get_names(pool, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_tool_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    bypass_cache: bool = False,
    **_kwargs,
) -> ComposedContextResponse:
    """tool page context — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("tool/page_context", {
            "profile_id": str(profile_id),
            "entity_id": str(entity_id) if entity_id else None,
        }),
        tags=["context", "tool", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ComposedContextResponse,
        builder=lambda: _page_context_tool_build(
            pool, redis,
            profile_id=profile_id,
            entity_id=entity_id,
        ),
        bypass_cache=bypass_cache,
    )


async def _page_context_tool_build(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
) -> ComposedContextResponse:
    """Tool page context.

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

    async def _get_tool_docs() -> list:
        async with pool.acquire() as conn:
            return await get_tool_docs(conn)

    async def _get_tool_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_tool_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_args_docs() -> list:
        async with pool.acquire() as conn:
            return await get_args_docs(conn)

    async def _get_arg_positions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_arg_positions_docs(conn)

    async def _get_args_outputs_docs() -> list:
        async with pool.acquire() as conn:
            return await get_args_outputs_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.tool.permissions_context import (
            resolve_tool_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_tool_permissions_context(conn, entity_id)

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
        args,
        arg_positions,
        args_outputs,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_tool_docs(),
        _get_tool_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_flags_docs(),
        _get_args_docs(),
        _get_arg_positions_docs(),
        _get_args_outputs_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.tool.permissions import (
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
        )
        caller_permissions.can_edit = compute_can_edit(
            profile.role_level,
            profile.role_permissions,
            entity_perms.active_agent_count,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.active_agent_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_permissions,
            entity_perms.active_agent_count,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = await build_profile_summary(pool, redis, profile)

    # -- Step 6: Starter prompts --------------------------------------------------

    prompts = OperationPrompts(prompts={
        "create": [
            StarterPrompt(title="Define a tool", content="Create a new function calling tool with input arguments, output schema, and description."),
            StarterPrompt(title="From API", content="I have an API endpoint — help me wrap it as a tool for agents to use."),
            StarterPrompt(title="Template-based", content="Create a tool from a common pattern like search, calculator, or data lookup."),
        ],
        "search": [
            StarterPrompt(title="Find tools", content="Help me find tools that match specific input types or functional capabilities."),
            StarterPrompt(title="Compare tools", content="Compare my tools and identify overlapping functionality or missing capabilities."),
            StarterPrompt(title="Audit tools", content="Review all tools and flag any with incomplete argument schemas or missing outputs."),
        ],
        "update": [
            StarterPrompt(title="Refine arguments", content="Improve this tool's input argument definitions, types, and validation."),
            StarterPrompt(title="Enhance output", content="Make this tool's output schema more structured and useful for agents."),
            StarterPrompt(title="Add description", content="Improve this tool's description so agents understand when and how to use it."),
        ],
        "duplicate": [
            StarterPrompt(title="Clone & modify", content="Duplicate this tool and adjust its arguments for a related but different function."),
            StarterPrompt(title="Variant tool", content="Create a variation of this tool with different output formatting or constraints."),
        ],
        "draft": [
            StarterPrompt(title="Draft tool", content="Start drafting a new tool — suggest a name, arguments, and output schema."),
            StarterPrompt(title="Iterate draft", content="Review my current draft and suggest improvements to the argument schema before saving."),
        ],
        "export": [
            StarterPrompt(title="Export catalog", content="Generate a summary of all tools with their arguments and descriptions."),
            StarterPrompt(title="Export analysis", content="Analyze my tools and create a report on coverage and argument consistency."),
        ],
    })

    # -- Step 7: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.tool.create import create_tool
    from app.routes.tool.delete import delete_tool
    from app.routes.tool.draft import patch_tool_draft
    from app.routes.tool.duplicate import duplicate_tool
    from app.routes.tool.export import export_tools
    from app.routes.tool.get import get_tool
    from app.routes.tool.search import search_tool
    from app.routes.tool.update import update_tool

    return ComposedContextResponse(
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
        permission_docs=[
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
        prompts=prompts,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
