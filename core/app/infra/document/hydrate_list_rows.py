"""Hydrate ``ListDocumentApiDocument`` rows for a specific set of document ids.

Used by create/duplicate/update impls to return the full row content
alongside their per-row status results — so the client's ghost rail can
materialize the new/changed row directly from the audit ``.completed``
payload, no ``router.refresh()`` needed (which would re-burst the page's
SSR fetches).

This is a focused subset of ``_search_document_build``'s flow: the row
hydration steps (get artifacts → resolve junctions → hydrate names +
files + flags → compute permissions), without the facet aggregation,
pagination, or big-cache wrap that the search route layers on top.
"""

from __future__ import annotations

import asyncio
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
from app.infra.document.types import ListDocumentApiDocument
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.document.get import get_documents
from app.tools.resources.files.get import get_files as get_uploads
from app.tools.resources.flags.get import get_flags
from app.tools.resources.names.get import get_names


def _extension_from_path(file_path: str | None) -> str | None:
    """Derive a lowercase file extension (no dot) from an uploads_entry.file_path."""
    if not file_path:
        return None
    name = file_path.rsplit("/", 1)[-1]
    if "." not in name:
        return None
    ext = name.rsplit(".", 1)[1].strip().lower()
    return ext or None


async def hydrate_document_list_rows(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    document_ids: list[UUID],
) -> list[ListDocumentApiDocument]:
    """Return ``ListDocumentApiDocument`` rows for the given document ids.

    Mirrors ``_search_document_build``'s row-hydration steps minus
    facets and pagination. Active scenario counts are computed via
    ``resolve_document_permissions_context`` (the same call the search
    route makes), so they stay accurate for both fresh and updated
    rows.
    """
    if not document_ids:
        return []

    profile = await resolve_profile_identity_context(pool, profile_id, redis)
    if profile is None:
        return []

    user_role_level = profile.role_level
    user_department_ids = profile.department_ids

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

    if not artifacts:
        return []

    # Collect resource ids to hydrate in parallel.
    all_name_ids: list[UUID] = []
    all_files_ids: list[UUID] = []
    all_flag_ids: list[UUID] = []
    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_files_ids.extend(a.files_ids or [])
        all_flag_ids.extend(a.flag_ids or [])

    all_files_ids = list(set(all_files_ids))
    all_flag_ids = list(set(all_flag_ids))

    async def _names() -> list:
        return await get_names(pool, all_name_ids, redis) if all_name_ids else []

    async def _uploads() -> list:
        if not all_files_ids:
            return []
        async with pool.acquire() as conn:
            return await get_uploads(conn, all_files_ids, redis)

    async def _flag_rows() -> list:
        return await get_flags(pool, all_flag_ids, redis) if all_flag_ids else []

    async def _file_extensions() -> dict[UUID, str | None]:
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

    async def _fetch_perm(artifact_id: UUID) -> DocumentPermissionsContext:
        async with pool.acquire() as conn:
            return await resolve_document_permissions_context(conn, artifact_id)

    perm_tasks = [_fetch_perm(a.id) for a in artifacts]

    (
        names_data,
        uploads_data,  # noqa: F841 — kept for parity with search; not used downstream beyond presence
        flag_rows_data,
        extension_map,
        *perm_results,
    ) = await asyncio.gather(
        _names(),
        _uploads(),
        _flag_rows(),
        _file_extensions(),
        *perm_tasks,
    )

    name_map = {n.id: n for n in names_data}
    flag_meta_map: dict[UUID, tuple[str | None, bool | None]] = {
        f.id: (getattr(f, "type", None), getattr(f, "value", None))
        for f in flag_rows_data
        if getattr(f, "id", None)
    }

    rows: list[ListDocumentApiDocument] = []
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
        can_duplicate = compute_can_duplicate(
            role_level=user_role_level, role_permissions=profile.role_permissions,
        )

        # Resolve first file_id for preview thumbnail (mirrors search).
        file_id: UUID | None = (a.files_ids or [None])[0] if a.files_ids else None
        extension = extension_map.get(file_id) if file_id else None

        # Derive per-row template flag from flag_ids.
        is_template = False
        for fid in a.flag_ids or []:
            ftype, fvalue = flag_meta_map.get(fid, (None, None))
            if ftype == "document_template" and fvalue is True:
                is_template = True
                break

        rows.append(
            ListDocumentApiDocument(
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
                can_edit=can_edit,
                can_duplicate=can_duplicate,
                can_delete=can_delete,
                updated_at=a.updated_at,
            )
        )

    return rows
