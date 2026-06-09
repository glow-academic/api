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

from app.infra.api_types import ListFilterOption, ListFilterSection
from app.infra.document.permissions import (
    compute_can_delete,
    compute_can_duplicate,
    compute_can_edit,
)
from app.infra.document.permissions_context import (
    DocumentPermissionsContext,
    resolve_document_permissions_context,
)
from app.infra.document.types import (
    ListDocumentApiDocument,
    ListDocumentApiResponse,
)
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.server_timing import timed
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.search import search_documents
from app.tools.resources.departments.search import search_departments
from app.tools.resources.fields.search import (
    search_fields as search_fields_resource,
)
from app.tools.resources.documents.get import (
    get_documents as get_document_resources,
)
from app.tools.resources.files.get import get_files as get_uploads
from app.tools.resources.flags.get import get_flags
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.get import get_names
from app.tools.resources.scenarios.search import (
    search_scenarios as search_scenarios_resource,
)
from app.utils.cache.big import (
    DEFAULT_BIG_CACHE_TTL_S,
    big_cache_key,
    get_or_build,
)


def _extension_from_path(file_path: str | None) -> str | None:
    """Derive a lowercase file extension (no dot) from an uploads_entry.file_path."""
    if not file_path:
        return None
    name = file_path.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].strip().lower()
    return ext or None

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
    search: str | None = None,
    scenario_ids: list[UUID] | None = None,
    field_ids: list[UUID] | None = None,
    filter_department_ids: list[UUID] | None = None,
    scenario_search: str | None = None,
    field_search: str | None = None,
    department_search: str | None = None,
    flag_search: str | None = None,
    page_size: int = 12,
    page_offset: int = 0,
    bypass_cache: bool = False,
    **_kwargs,
) -> ListDocumentApiResponse:
    """document search — big-cache wrapped."""
    return await get_or_build(
        redis=redis,
        key=big_cache_key("document/search", {
            "profile_id": str(profile_id),
            "search": search,
            "scenario_ids": [str(x) for x in scenario_ids] if scenario_ids else None,
            "field_ids": [str(x) for x in field_ids] if field_ids else None,
            "filter_department_ids": [str(x) for x in filter_department_ids] if filter_department_ids else None,
            "scenario_search": scenario_search,
            "field_search": field_search,
            "department_search": department_search,
            "flag_search": flag_search,
            "page_size": page_size,
            "page_offset": page_offset,
        }),
        tags=["search", "document", "artifacts"],
        ttl_s=DEFAULT_BIG_CACHE_TTL_S,
        response_model=ListDocumentApiResponse,
        builder=lambda: _search_document_build(
            pool, redis,
            profile_id=profile_id,
            search=search,
            scenario_ids=scenario_ids,
            field_ids=field_ids,
            filter_department_ids=filter_department_ids,
            scenario_search=scenario_search,
            field_search=field_search,
            department_search=department_search,
            flag_search=flag_search,
            page_size=page_size,
            page_offset=page_offset,
        ),
        bypass_cache=bypass_cache,
    )


async def _search_document_build(
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
    flag_search: str | None = None,
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

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids
    actor_name = profile.name

    # -- Step 2: Search documents --
    # The artifact search tool handles scenario_ids and field_ids filters internally

    with timed("query"):
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

        # Merge pending ledger entries so dormant create/duplicate rows
        # (and pending soft-deletes) surface in the list as ghost cards.
        from app.tools.entries.soft_calls.search import search_soft_calls
        pending_entries = await search_soft_calls(
            conn, redis, artifact="document", status="pending", limit=1000,
        )
    pending_ledger_ids = [e.artifact_id for e in pending_entries]
    ledger_by_artifact_id = {e.artifact_id: e for e in pending_entries}

    merged_ids: list[UUID] = []
    seen: set[UUID] = set()
    for did in [*document_ids, *pending_ledger_ids]:
        if did in seen:
            continue
        seen.add(did)
        merged_ids.append(did)
    added = sum(1 for did in pending_ledger_ids if did not in set(document_ids))
    total_count = total_count + added

    if not merged_ids:
        return _empty_response(actor_name, total_count=total_count)

    # -- Step 3: Get document artifacts with junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_documents(
            conn,
            merged_ids,
            names=True,
            departments=True,
            flags=True,
            files=True,
            documents=True,
            active=None,
        )

    # -- Step 3b: Resolve canonical content ids (file_id / text_id) --
    # A document's content (the file or HTML/text the viewer renders) lives on
    # ``documents_resource`` — reached via the ``document_documents_junction``
    # (exposed as ``a.document_ids``). The artifact-level ``document_files_junction``
    # is NOT where seeded docs keep their content, so resolving file_id from
    # ``a.files_ids`` alone yields null and never surfaces text_id. Mirror the
    # attempt/scenario context path and read file_id/text_id off the resource.
    all_doc_resource_ids = list(
        {a.document_ids[0] for a in artifacts if a.document_ids}
    )
    doc_resources = await get_document_resources(pool, all_doc_resource_ids, redis)
    doc_resource_map = {r.id: r for r in doc_resources}

    resolved_file_id: dict[UUID, UUID | None] = {}
    resolved_text_id: dict[UUID, UUID | None] = {}
    for a in artifacts:
        primary_doc_id = (a.document_ids or [None])[0]
        res = doc_resource_map.get(primary_doc_id) if primary_doc_id else None
        resolved_file_id[a.id] = res.file_id if res else None
        resolved_text_id[a.id] = res.text_id if res else None

    # -- Step 4: Parallel hydration + facets --

    all_name_ids: list[UUID] = []
    all_files_ids: list[UUID] = []
    all_flag_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_files_ids.extend(a.files_ids or [])
        all_flag_ids.extend(a.flag_ids or [])

    # Fold the resolved resource file_ids into the set so the upload/extension
    # hydration (thumbnail + extension chip) covers them too.
    all_files_ids.extend(fid for fid in resolved_file_id.values() if fid)

    # Deduplicate files IDs
    all_files_ids = list(set(all_files_ids))
    all_flag_ids = list(set(all_flag_ids))

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_uploads() -> list:
        if not all_files_ids:
            return []
        async with pool.acquire() as conn:
            return await get_uploads(conn, all_files_ids, redis)

    async def _fetch_flag_rows() -> list:
        if not all_flag_ids:
            return []
        return await get_flags(pool, all_flag_ids, redis)

    async def _fetch_file_extensions() -> dict[UUID, str | None]:
        """Map files_resource.id -> file extension via file_uploads_entry + uploads_entry."""
        if not all_files_ids:
            return {}
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (fue.file_id) fue.file_id, ue.file_path
                FROM file_uploads_entry fue
                JOIN uploads_entry ue ON ue.id = fue.upload_id
                WHERE fue.active = true
                  AND fue.file_id = ANY($1)
                ORDER BY fue.file_id, fue.created_at DESC
                """,
                all_files_ids,
            )
        return {r["file_id"]: _extension_from_path(r["file_path"]) for r in rows}

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

    async def _fetch_flag_facet() -> list:
        async with pool.acquire() as conn:
            return await search_flags(
                conn, redis, search=flag_search, document=True, limit_count=100
            )

    # Per-document permissions context (gives us active_scenario_count)
    async def _fetch_perm(artifact_id: UUID) -> DocumentPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_document_permissions_context(conn, artifact_id)

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]

    with timed("hydrate"):
        (
            names_data,
            uploads_data,
            flag_rows_data,
            extension_map,
            scenario_facet,
            field_facet,
            department_facet,
            flag_facet,
            *perm_results,
        ) = await asyncio.gather(
            _fetch_names(),
            _fetch_uploads(),
            _fetch_flag_rows(),
            _fetch_file_extensions(),
            _fetch_scenario_facet(),
            _fetch_field_facet(),
            _fetch_department_facet(),
            _fetch_flag_facet(),
            *perm_tasks,
        )

    # Build flag lookup: id -> (type, value) so we can derive booleans per-row
    flag_meta_map: dict[UUID, tuple[str | None, bool | None]] = {
        f.id: (getattr(f, "type", None), getattr(f, "value", None))
        for f in flag_rows_data
        if getattr(f, "id", None)
    }

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

    with timed("build"):
     for i, a in enumerate(artifacts):
        name_obj = name_map.get(a.name_ids[0]) if a.name_ids else None

        dept_ids_str = [str(d) for d in (a.department_ids or [])]
        active_scenario_count = perm_results[i].active_scenario_count

        is_inactive = not a.active

        can_edit = compute_can_edit(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            document_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
            user_department_ids=user_department_ids,
        )
        can_delete = compute_can_delete(
            role_level=user_role_level, role_permissions=profile.role_permissions,
            document_department_ids=dept_ids_str,
            active_scenario_count=active_scenario_count,
        )
        can_duplicate = compute_can_duplicate(role_level=user_role_level, role_permissions=profile.role_permissions)

        # Canonical content ids from documents_resource (what the viewer fetches).
        file_id: UUID | None = resolved_file_id.get(a.id)
        text_id: UUID | None = resolved_text_id.get(a.id)
        extension = extension_map.get(file_id) if file_id else None

        # Derive per-row flag state booleans from flag_ids
        is_template = False
        for fid in a.flag_ids or []:
            ftype, fvalue = flag_meta_map.get(fid, (None, None))
            if ftype == "document_template" and fvalue is True:
                is_template = True
                break

        ledger = ledger_by_artifact_id.get(a.id)
        documents.append(
            ListDocumentApiDocument(
                id=a.id,

                document_id=a.id,
                name=name_obj.name if name_obj else None,
                department_ids=dept_ids_str,
                scenario_ids=None,
                field_ids=None,
                flag_ids=list(a.flag_ids or []),
                is_inactive=is_inactive,
                is_template=is_template,
                extension=extension,
                num_scenarios=active_scenario_count,
                active_scenario_count=active_scenario_count,
                file_id=file_id,
                text_id=text_id,
                pending_status=ledger.status if ledger else None,
                pending_operation=ledger.operation if ledger else None,
                pending_call_id=ledger.call_id if ledger else None,
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

    flag_filter = ListFilterSection(
        options=[
            ListFilterOption(id=str(f.id), name=f.name, type=f.type, count=0)
            for f in flag_facet
        ],
        search=flag_search,
    )

    return ListDocumentApiResponse(
        actor_name=actor_name,
        documents=documents,
        scenario_filter=scenario_filter,
        field_filter=field_filter,
        department_filter=department_filter,
        flag_filter=flag_filter,
        total_count=total_count,
        import_fields=DOCUMENT_IMPORT_FIELDS,
    )


# -- Helpers --


def _empty_response(
    actor_name: str | None = None, total_count: int = 0
) -> ListDocumentApiResponse:
    return ListDocumentApiResponse(
        actor_name=actor_name,
        documents=[],
        total_count=total_count,
        import_fields=DOCUMENT_IMPORT_FIELDS,
    )


async def _empty_list() -> list:
    return []
