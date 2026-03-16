"""Field export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_fields — full dump (all IDs, no filters, no pagination)
  3. get_fields — hydrate junction IDs
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
from app.tools.artifacts.field.get import get_fields
from app.tools.artifacts.field.search import search_fields
from app.tools.resources.conditional_parameters.get import (
    get_conditional_parameters,
)
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.parameters.get import get_parameters

PIPE = "|"

CSV_COLUMNS = [
    "field_id",
    "name",
    "description",
    "active",
    "departments",
    "conditional_parameters",
]


async def export_field_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    field_id: UUID | None = None,
) -> dict:
    """Field full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_fields → all IDs (full dump, no pagination)
      3. get_fields → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.field.types import ExportFieldApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all fields (full dump) ────────────────────────

    if field_id:
        field_ids = [field_id]
    else:
        async with pool.acquire() as conn:
            field_ids, _total_count = await search_fields(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not field_ids:
            return ExportFieldApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get field artifacts with all junction IDs ────────────

    async with pool.acquire() as conn:
        artifacts = await get_fields(
            conn,
            field_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            conditional_parameters=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_conditional_parameter_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_conditional_parameter_ids.extend(a.conditional_parameter_ids or [])

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

    async def _fetch_conditional_parameters() -> list:
        if not all_conditional_parameter_ids:
            return []
        async with pool.acquire() as conn:
            return await get_conditional_parameters(
                conn, all_conditional_parameter_ids, redis
            )

    (
        names_data,
        descriptions_data,
        departments_data,
        conditional_parameters_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_conditional_parameters(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}

    # Conditional parameters: two-hop (conditional_parameter → parameter → name)
    cp_param_id_map = {cp.id: cp.parameter_id for cp in conditional_parameters_data}
    all_param_ids = list({pid for pid in cp_param_id_map.values() if pid})
    if all_param_ids:
        async with pool.acquire() as conn:
            params_data = await get_parameters(conn, all_param_ids, redis)
    else:
        params_data = []
    param_name_map = {p.id: p.name for p in params_data}
    cp_name_map = {
        cp_id: param_name_map.get(param_id, "")
        for cp_id, param_id in cp_param_id_map.items()
        if param_id
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
        cp_str = PIPE.join(
            cp_name_map.get(cpid, "") for cpid in (a.conditional_parameter_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                cp_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"fields_export_{timestamp}.csv"

    return ExportFieldApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
