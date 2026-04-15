"""Document page context — docs + profile identity + evaluated permissions.

Superset of docs.py. A single endpoint that gives the client everything
it needs to render the document page:
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
    ProfileSummary,
)
from app.infra.docs_helper import PageMetadataConfig, compute_docs_metadata
from app.infra.profile_identity_context import resolve_profile_identity_context

# Artifact tool docs
from app.tools.artifacts.document.docs import get_document_docs
from app.tools.artifacts.document.get import (
    get_documents as get_document_artifacts,
)

# Entry tool docs
from app.tools.entries.document_drafts.docs import get_document_drafts_docs

# Resource tool docs
from app.tools.resources.departments.docs import get_departments_docs
from app.tools.resources.descriptions.docs import get_descriptions_docs
from app.tools.resources.fields.docs import get_fields_docs
from app.tools.resources.files.docs import get_files_docs
from app.tools.resources.flags.docs import get_flags_docs
from app.tools.resources.images.docs import get_images_docs
from app.tools.resources.names.docs import get_names_docs

# Name hydration
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.docs import (
    get_parameter_fields_docs,
)
from app.tools.resources.parameters.docs import get_parameters_docs
from app.tools.resources.texts.docs import get_texts_docs

_PAGE_METADATA = PageMetadataConfig(
    list_title="Documents",
    list_description="Manage structured content templates.",
    detail_title="— Document",
    detail_description="View and edit document configuration and linked resources.",
    new_title="New Document",
    new_description="Create a new document.",
)


async def _resolve_entity_name(
    pool: asyncpg.Pool,
    redis: Redis,
    entity_id: UUID,
) -> str | None:
    """Get display name for a document by ID using black-box tools."""
    async with pool.acquire() as conn:
        artifacts = await get_document_artifacts(conn, [entity_id], names=True)
        if not artifacts or not artifacts[0].name_ids:
            return None
        names_data = await get_names(conn, artifacts[0].name_ids, redis)
    return names_data[0].name if names_data else None


async def page_context_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    entity_id: UUID | None = None,
    **_kwargs,
) -> ComposedContextResponse:
    """Document page context — superset of docs_document_impl.

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

    async def _get_document_docs() -> list:
        async with pool.acquire() as conn:
            return await get_document_docs(conn)

    async def _get_document_drafts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_document_drafts_docs(conn)

    async def _get_names_docs() -> list:
        async with pool.acquire() as conn:
            return await get_names_docs(conn)

    async def _get_descriptions_docs() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions_docs(conn)

    async def _get_departments_docs() -> list:
        async with pool.acquire() as conn:
            return await get_departments_docs(conn)

    async def _get_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_fields_docs(conn)

    async def _get_files_docs() -> list:
        async with pool.acquire() as conn:
            return await get_files_docs(conn)

    async def _get_flags_docs() -> list:
        async with pool.acquire() as conn:
            return await get_flags_docs(conn)

    async def _get_images_docs() -> list:
        async with pool.acquire() as conn:
            return await get_images_docs(conn)

    async def _get_parameter_fields_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameter_fields_docs(conn)

    async def _get_parameters_docs() -> list:
        async with pool.acquire() as conn:
            return await get_parameters_docs(conn)

    async def _get_texts_docs() -> list:
        async with pool.acquire() as conn:
            return await get_texts_docs(conn)

    async def _get_entity_perms():
        if not entity_id:
            return None
        from app.infra.document.permissions_context import (
            resolve_document_permissions_context,
        )
        async with pool.acquire() as conn:
            return await resolve_document_permissions_context(conn, entity_id)

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
        fields,
        files,
        flags,
        images,
        parameter_fields,
        parameters,
        texts,
        entity_perms,
        entity_name,
    ) = await asyncio.gather(
        _get_document_docs(),
        _get_document_drafts_docs(),
        _get_names_docs(),
        _get_descriptions_docs(),
        _get_departments_docs(),
        _get_fields_docs(),
        _get_files_docs(),
        _get_flags_docs(),
        _get_images_docs(),
        _get_parameter_fields_docs(),
        _get_parameters_docs(),
        _get_texts_docs(),
        _get_entity_perms(),
        _get_entity_name(),
    )

    # -- Step 3: Page metadata --------------------------------------------------

    page_metadata = compute_docs_metadata(_PAGE_METADATA, entity_name)

    # -- Step 4: Evaluate caller permissions ------------------------------------

    from app.infra.document.permissions import (
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
            entity_perms.active_scenario_count,
            profile.department_ids,
        )
        caller_permissions.can_delete = compute_can_delete(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_scenario_count,
        )
        caller_permissions.disabled_reason = compute_disabled_reason(
            profile.role_level,
            profile.role_permissions,
            entity_perms.department_ids,
            entity_perms.active_scenario_count,
            profile.department_ids,
        )

    # -- Step 5: Build profile summary ------------------------------------------

    profile_summary = ProfileSummary(
        name=profile.name,
        role=profile.role,
        role_level=profile.role_level,
        department_ids=profile.department_ids,
        artifact_access=profile.role_artifacts,
        is_active=profile.is_active,
    )

    # -- Step 6: Assemble response ----------------------------------------------

    # Lazy imports to avoid circular dependencies
    from app.routes.document.create import create_document
    from app.routes.document.delete import delete_document
    from app.routes.document.draft import patch_document_draft
    from app.routes.document.duplicate import duplicate_document
    from app.routes.document.export import export_documents
    from app.routes.document.get import get_document
    from app.routes.document.search import search_document
    from app.routes.document.update import update_document

    return ComposedContextResponse(
        name="document",
        type="artifact",
        description=(
            "Documents define structured content templates. "
            "Each document links to resources (names, descriptions, departments, "
            "fields, files, flags, images, parameter_fields, parameters, texts) "
            "via junction tables."
        ),
        artifact=artifact,
        entries=[drafts],
        resources=[
            names,
            descriptions,
            departments,
            fields,
            files,
            flags,
            images,
            parameter_fields,
            parameters,
            texts,
        ],
        permission_docs=[
            get_operation_info(
                has_access,
                description="View access — user shares ANY department with the document.",
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
                get_document,
                description="POST /get — Get a single document by ID with hydrated resources.",
            ),
            get_operation_info(
                search_document,
                description="POST /search — Paginated document search with filters.",
            ),
            get_operation_info(
                create_document,
                description="POST /create — Create a new document artifact.",
            ),
            get_operation_info(
                update_document,
                description="POST /update — Update an existing document's resource links.",
            ),
            get_operation_info(
                duplicate_document,
                description="POST /duplicate — Duplicate an existing document.",
            ),
            get_operation_info(
                delete_document,
                description="POST /delete — Delete a document.",
            ),
            get_operation_info(
                patch_document_draft,
                description="PATCH /draft — Create or patch a document draft (autosave).",
            ),
            get_operation_info(
                export_documents,
                description="POST /export — Export documents as denormalized CSV.",
            ),
        ],
        page_metadata=page_metadata,
        profile=profile_summary,
        caller_permissions=caller_permissions,
    )
