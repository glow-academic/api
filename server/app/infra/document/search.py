"""Document search logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments, name)
  2. search_documents — core artifact search (IDs + total_count)
  3. get_documents — hydrate junction IDs
  4. Resource get tools — hydrate names, files (uploads)
  5. Permissions — compute per-document can_edit, can_delete, can_duplicate
  6. Facets — parallel resource/artifact searches for filter options
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.document.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.document.permissions_context import (
    DocumentPermissionsContext,
    resolve_document_permissions_context,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.document.types import (
    ListDocumentApiDocument,
    ListDocumentApiResponse,
)
from app.infra.v5_types import ListFilterOption, ListFilterSection
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.search import search_documents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.fields.search import (
    search_fields as search_fields_resource,
)
from app.tools.resources.files.get import get_files as get_uploads
from app.tools.resources.names.get import get_names
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenarios_resource,
)

DOCUMENT_IMPORT_FIELDS: list[dict[str, Any]] = [
    {
        "key": "name",
        "label": "Name",
        "required": True,
        "example": "Patient Intake Form",
        "description": "The document's display name",
    },
    {
        "key": "description",
        "label": "Description",
        "example": "Standard intake form for new patients...",
        "description": "Optional description",
    },
    {
        "key": "is_inactive",
        "label": "Inactive",
        "type": "boolean",
        "example": "false",
        "description": "Whether the document is inactive (true/false)",
    },
    {
        "key": "departments",
        "label": "Departments",
        "multi": True,
        "example": "Nursing, Medicine",
        "description": "Comma-separated department names",
    },
]


async def search_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    # Main filters
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    # Facet search text
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    # Pagination
    page_size: int = 12,
    page_offset: int = 0,
) -> ListDocumentApiResponse:
    """Document search using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, departments, name
      2. search_documents -> (document_artifact_ids, total_count)
      3. get_documents -> hydrate junction IDs
      4. Parallel: hydrate resources + compute permissions + facets
      5. Hydrate upload_id from files_resource
    """
    from fastapi import HTTPException

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role = profile.role
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # -- Step 2: Search documents --
    # The artifact search tool handles scenario_ids and field_ids filters internally

    async with pool.acquire() as conn:
        document_ids, total_count = await search_documents(
            conn,
            search=search,
            department_ids=filter_department_ids,
            scenario_ids=scenario_ids,
            field_ids=field_ids,
            limit_count=page_size,
            offset_count=page_offset,
        )

    if not document_ids:
        return _empty_response(actor_name, total_count=0)

    # -- Step 3: Get document artifacts with junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_documents(
            conn,
            document_ids,
            names=True,
            departments=True,
            flags=True,
            files=True,
            documents=True,
        )

    # -- Step 4: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_files_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_files_ids.extend(a.files_ids or [])

    # Deduplicate files IDs
    all_files_ids = list(set(all_files_ids))

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_uploads() -> list:
        if not all_files_ids:
            return []
        async with pool.acquire() as conn:
            return await get_uploads(conn, all_files_ids, redis)

    async def _fetch_scenario_facet() -> list:
        async with pool.acquire() as conn:
            return await search_scenarios_resource(
                conn, redis, search=scenario_search, scenario=True, limit_count=100
            )

    async def _fetch_field_facet() -> list:
        async with pool.acquire() as conn:
            return await search_fields_resource(
                conn, redis, search=field_search, parameter=True, limit_count=100
            )

    async def _fetch_department_facet() -> list:
        async with pool.acquire() as conn:
            return await search_departments(
                conn, redis, search=department_search, document=True, limit_count=100
            )

    # Per-document permissions context (gives us active_scenario_count)
    async def _fetch_perm(artifact_id: UUID) -> DocumentPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_document_permissions_context(conn, artifact_id)

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]

    (
        names_data,
        uploads_data,
        scenario_facet,
        field_facet,
        department_facet,
        *perm_results,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_uploads(),
        _fetch_scenario_facet(),
        _fetch_field_facet(),
        _fetch_department_facet(),
        *perm_tasks,
    )

    # Build lookup maps
    name_map = {n.id: n for n in names_data}
    # Build files_resource ID -> upload_id map
    upload_resource_to_file_id: dict[UUID, UUID] = {}
    for u in uploads_data:
        if u.id:
            # files_resource.id is the upload_id for download
            upload_resource_to_file_id[u.id] = u.id

    # -- Step 5: Build document list with permissions --

    documents: list[ListDocumentApiDocument] = []

    for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_scenario_count = perm_results[i].active_scenario_count

        is_inactive = not a.active

        can_edit = compute_can_edit(
            user_role=user_role,
            document_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            user_role=user_role,
            document_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
        )
        can_duplicate = compute_can_duplicate(user_role)

        # Resolve upload_id from files_ids
        upload_id: UUID | None = None
        for fid in a.files_ids or []:
            if fid in upload_resource_to_file_id:
                upload_id = upload_resource_to_file_id[fid]
                break

        documents.append(
            ListDocumentApiDocument(
                document_id=a.id,
                name=name_obj.name if name_obj else None,
                department_ids=dept_ids_str,
                scenario_ids=None,
                field_ids=None,
                is_inactive=is_inactive,
                num_scenarios=active_scenario_count,
                active_scenario_count=active_scenario_count,
                upload_id=upload_id,
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    # -- Step 6: Build facet sections --

    scenario_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(s.id), name=s.name, count=0) for s in scenario_facet
        ],
        selected_ids=[str(sid) for sid in scenario_ids] if scenario_ids else None,
        search=scenario_search,
    )

    field_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, count=0) for f in field_facet
        ],
        selected_ids=[str(fid) for fid in field_ids] if field_ids else None,
        search=field_search,
    )

    department_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(d.id), name=d.name, count=0)
            for d in department_facet
        ],
        selected_ids=[str(did) for did in filter_department_ids]
        if filter_department_ids
        else None,
        search=department_search,
    )

    return ListDocumentApiResponse(
        actor_name=actor_name,
        documents=documents,
        scenario_filter=scenario_filter,
        field_filter=field_filter,
        department_filter=department_filter,
        total_count=total_count,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListDocumentApiResponse:
    return ListDocumentApiResponse(
        actor_name=actor_name,
        documents=[],
        total_count=total_count,
    )


async def _empty_list() -> list:
    return []
