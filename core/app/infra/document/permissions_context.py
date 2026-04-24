"""Document permissions context + shared save helpers.

Permissions context:
  1. resolve_document_permissions_context — lightweight access + edit check

Shared save helpers (used by both create and update):
  2. resolve_document_values — raw string → resource ID resolution
  3. create_denormalized_snapshot — hydrate IDs → documents_resource snapshot

Composes existing black-box fetchers — no raw SQL.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.tools.artifacts.document.get import (
    get_documents as get_document_artifacts,
)
from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.resources.departments.search import search_departments
from app.tools.resources.descriptions.create import create_description
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.documents.create import (
    create_document as create_document_resource,
)
from app.tools.resources.flags.search import search_flags
from app.tools.resources.names.create import create_name
from app.tools.resources.names.get import get_names

if TYPE_CHECKING:
    from app.infra.document.types import (
        CreateDocumentItem,
        DocumentFieldError,
        UpdateDocumentItem,
    )


@dataclass(frozen=True)
class DocumentPermissionsContext:
    """Lightweight context for document permission checks."""

    exists: bool
    department_ids: list[UUID]
    active_scenario_count: int


async def resolve_document_permissions_context(
    conn: asyncpg.Connection,
    document_id: UUID,
) -> DocumentPermissionsContext:
    """Fetch just what's needed for document permission checks.

    Two black-box tool calls:
      1. get_document_artifacts → department_ids + document_ids (resource IDs)
      2. search_scenarios → any active scenarios using this document?
    """
    artifacts = await get_document_artifacts(
        conn,
        [document_id],
        departments=True,
        documents=True,
    )

    if not artifacts:
        return DocumentPermissionsContext(
            exists=False,
            department_ids=[],
            active_scenario_count=0,
        )

    artifact = artifacts[0]
    department_ids = list(artifact.department_ids or [])
    document_resource_ids = list(artifact.document_ids or [])

    _, total = (
        await search_scenarios(
            conn,
            document_ids=document_resource_ids,
            active_only=True,
            limit_count=1,
        )
        if document_resource_ids
        else ([], 0)
    )

    return DocumentPermissionsContext(
        exists=True,
        department_ids=department_ids,
        active_scenario_count=total,
    )


# ---------------------------------------------------------------------------
# Shared save helpers — used by both document_create and document_update
# ---------------------------------------------------------------------------


async def resolve_document_values(
    conn: asyncpg.Connection,
    redis: Redis,
    item: CreateDocumentItem | UpdateDocumentItem,
    is_create: bool,
) -> list[DocumentFieldError]:
    """Resolve raw value fields to resource IDs (mutates item in place).

    For 'create' resources (name, description):
      Creates a new resource via the create tool.
    For 'match' resources (departments, flags):
      Searches by name via the search tool, matches exact (case-insensitive).

    Returns a list of errors (empty if all resolved).
    """
    from app.infra.document.types import DocumentFieldError

    errors: list[DocumentFieldError] = []

    # --- Create resources ---

    if item.name is not None and item.name_id is None:
        result = await create_name(conn, item.name, redis)
        item.name_id = result.id

    if item.description is not None and item.description_id is None:
        result = await create_description(conn, item.description, redis)
        item.description_id = result.id

    # --- Resolve denormalized flag booleans → canonical flag_ids entries ---

    denorm_flag_values: dict[str, bool] = {}
    if item.active is not None:
        denorm_flag_values["document_active"] = bool(item.active)
    if denorm_flag_values:
        all_flags = await search_flags(
            conn,
            redis,
            search=None,
            limit_count=200,
            bypass_cache=True,
        )
        resolved_flag_ids: list[UUID] = list(item.flag_ids or [])
        seen = set(resolved_flag_ids)
        for flag_type, desired_value in denorm_flag_values.items():
            match = next(
                (
                    f
                    for f in all_flags
                    if (
                        getattr(f, "type", None) == flag_type
                        or getattr(f, "name", None) == flag_type
                    )
                    and getattr(f, "value", None) is desired_value
                ),
                None,
            )
            if match and match.id and match.id not in seen:
                resolved_flag_ids.append(match.id)
                seen.add(match.id)
            elif not match:
                errors.append(
                    DocumentFieldError(
                        field=flag_type,
                        message=(
                            f"Flag row not found for type={flag_type} "
                            f"value={desired_value}"
                        ),
                    )
                )
        item.flag_ids = resolved_flag_ids

    if item.departments is not None and item.department_ids is None:
        all_depts = await search_departments(
            conn,
            redis,
            search=None,
            limit_count=1000,
        )
        dept_name_map = {d.name.lower(): d.id for d in all_depts if d.name and d.id}
        resolved_ids = []
        for dept_name in item.departments:
            dept_id = dept_name_map.get(dept_name.lower())
            if dept_id:
                resolved_ids.append(dept_id)
            else:
                errors.append(
                    DocumentFieldError(
                        field="departments",
                        message=f'Department "{dept_name}" not found',
                    )
                )
        if not any(e.field == "departments" for e in errors):
            item.department_ids = resolved_ids

    # --- Validate required fields (create only) ---

    if is_create:
        if item.name_id is None:
            errors.append(DocumentFieldError(field="name", message="Name is required"))

    return errors


async def create_denormalized_snapshot(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    id: UUID | None = None,
    name_id: UUID | None,
    description_id: UUID | None,
    department_ids: list[UUID] | None = None,
    image_ids: list[UUID] | None = None,
    parameter_field_ids: list[UUID] | None = None,
    template: bool = False,
    file_id: UUID | None = None,
    text_id: UUID | None = None,
) -> UUID:
    """Create a documents_resource snapshot by hydrating IDs to values.

    Each parallel branch acquires its own connection from the pool.
    """

    async def _get_names() -> list:
        if not name_id:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, [name_id], redis, bypass_cache=True)

    async def _get_descriptions() -> list:
        if not description_id:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(
                conn, [description_id], redis, bypass_cache=True
            )

    names, descriptions = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
    )

    async with pool.acquire() as conn:
        result = await create_document_resource(
            conn,
            redis,
            id=id,
            name=names[0].name if names else "",
            description=descriptions[0].description if descriptions else "",
            department_ids=department_ids,
            image_ids=image_ids,
            parameter_field_ids=parameter_field_ids,
            template=template,
            file_id=file_id,
            text_id=text_id,
        )
    return result.id
