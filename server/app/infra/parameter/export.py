"""Parameter export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_parameters — full dump (all IDs, no filters, no pagination)
  3. get_parameters — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, fields)
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
from app.tools.artifacts.parameter.get import get_parameters
from app.tools.artifacts.parameter.search import search_parameters
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.fields.get import get_fields
from app.tools.resources.names.get import get_names

PIPE = "|"

CSV_COLUMNS = [
    "parameter_id",
    "name",
    "description",
    "active",
    "departments",
    "fields",
]


async def export_parameter_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    parameter_id: UUID | None = None,
) -> dict:
    """Parameter full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_parameters → all IDs (full dump, no pagination)
      3. get_parameters → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.parameter.types import ExportParameterApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all parameters (full dump) ────────────────────

    if parameter_id:
        parameter_ids = [parameter_id]
    else:
        async with pool.acquire() as conn:
            parameter_ids, _total_count = await search_parameters(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not parameter_ids:
            return ExportParameterApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get parameter artifacts with all junction IDs ────────

    async with pool.acquire() as conn:
        artifacts = await get_parameters(
            conn,
            parameter_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            fields=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    # Collect all resource IDs across artifacts
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_field_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_field_ids.extend(a.field_ids or [])

    async def _empty() -> list:
        return []

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _get_fields() -> list:
        if not all_field_ids:
            return []
        async with pool.acquire() as conn:
            return await get_fields(conn, all_field_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        fields_data,
    ) = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_departments(),
        _get_fields(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    field_map = {f.id: f.name for f in fields_data}

    # ── Step 5: Generate CSV + upload ──────────────────────────────────

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_COLUMNS)

    for a in artifacts:
        # Single-select: first resource value
        name = name_map.get(a.name_ids[0], "") if a.name_ids else ""
        description = (
            description_map.get(a.description_ids[0], "") if a.description_ids else ""
        )

        # Active flag
        active = "Yes" if a.active else "No"

        # Multi-select: pipe-delimited values
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        fields_str = PIPE.join(field_map.get(fid, "") for fid in (a.field_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                fields_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"parameters_export_{timestamp}.csv"

    return ExportParameterApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
