"""Document export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_documents — full dump (all IDs, no filters, no pagination)
  3. get_documents — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, etc.)
  5. CSV generation + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.document.get import get_documents
from app.tools.artifacts.document.search import search_documents
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.fields.get import get_fields
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.get import get_parameter_fields

PIPE = "|"

CSV_COLUMNS = [
    "document_id",
    "name",
    "description",
    "active",
    "departments",
    "parameter_fields",
]


async def export_document_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    document_id: UUID | None = None,
) -> dict:
    """Document full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_documents → all IDs (full dump, no pagination)
      3. get_documents → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.document.types import ExportDocumentApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all documents (full dump) ────────────────────────

    if document_id:
        document_ids = [document_id]
    else:
        async with pool.acquire() as conn:
            document_ids, _total_count = await search_documents(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not document_ids:
            return ExportDocumentApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get document artifacts with all junction IDs ────────────

    async with pool.acquire() as conn:
        artifacts = await get_documents(
            conn,
            document_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            parameter_fields=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_parameter_field_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_parameter_field_ids.extend(a.parameter_field_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _fetch_parameter_fields() -> list:
        if not all_parameter_field_ids:
            return []
        async with pool.acquire() as conn:
            return await get_parameter_fields(conn, all_parameter_field_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        parameter_fields_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_parameter_fields(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}

    # Parameter fields: two-hop (parameter_field → field → name)
    pf_field_id_map = {pf.id: pf.field_id for pf in parameter_fields_data}
    all_field_ids = list({fid for fid in pf_field_id_map.values() if fid})
    async with pool.acquire() as conn:
        fields_data = (
            await get_fields(conn, all_field_ids, redis) if all_field_ids else []
        )
    field_name_map = {f.id: f.name for f in fields_data}
    pf_name_map = {
        pf_id: field_name_map.get(field_id, "")
        for pf_id, field_id in pf_field_id_map.items()
        if field_id
    }

    # ── Step 5: Generate CSV + upload ──────────────────────────────────

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    for a in artifacts:
        name = name_map.get(a.name_ids[0], "") if a.name_ids else ""
        description = (
            description_map.get(a.description_ids[0], "") if a.description_ids else ""
        )
        active = "Yes" if a.active else "No"
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        pf_str = PIPE.join(
            pf_name_map.get(pfid, "") for pfid in (a.parameter_field_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                pf_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"documents_export_{timestamp}.csv"

    return ExportDocumentApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
