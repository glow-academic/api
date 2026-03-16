"""Rubric export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_rubrics — full dump (all IDs, no filters, no pagination)
  3. get_rubrics — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, points, standard_groups, standards)
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
from app.tools.artifacts.rubric.get import get_rubrics
from app.tools.artifacts.rubric.search import search_rubrics
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.points.get import get_points
from app.tools.resources.standard_groups.get import get_standard_groups
from app.tools.resources.standards.get import get_standards

PIPE = "|"

CSV_COLUMNS = [
    "rubric_id",
    "name",
    "description",
    "active",
    "departments",
    "points",
    "standard_groups",
    "standards",
]


async def export_rubric_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    rubric_id: UUID | None = None,
) -> dict:
    """Rubric full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_rubrics → all IDs (full dump, no pagination)
      3. get_rubrics → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.rubric.types import ExportRubricApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all rubrics (full dump) ───────────────────────

    if rubric_id:
        rubric_ids = [rubric_id]
    else:
        async with pool.acquire() as conn:
            rubric_ids, _total_count = await search_rubrics(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not rubric_ids:
            return ExportRubricApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get rubric artifacts with all junction IDs ───────────

    async with pool.acquire() as conn:
        artifacts = await get_rubrics(
            conn,
            rubric_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            points=True,
            standard_groups=True,
            standards=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    # Collect all resource IDs across artifacts
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_point_ids: list[UUID] = []
    all_standard_group_ids: list[UUID] = []
    all_standard_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_point_ids.extend(a.point_ids or [])
        all_standard_group_ids.extend(a.standard_group_ids or [])
        all_standard_ids.extend(a.standard_ids or [])

    async def _empty() -> list:
        return []

    async def _get_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _get_points() -> list:
        async with pool.acquire() as conn:
            return await get_points(conn, all_point_ids, redis)

    async def _get_standard_groups() -> list:
        async with pool.acquire() as conn:
            return await get_standard_groups(conn, all_standard_group_ids, redis)

    async def _get_standards() -> list:
        async with pool.acquire() as conn:
            return await get_standards(conn, all_standard_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        points_data,
        standard_groups_data,
        standards_data,
    ) = await asyncio.gather(
        _get_names() if all_name_ids else _empty(),
        _get_descriptions() if all_description_ids else _empty(),
        _get_departments() if all_department_ids else _empty(),
        _get_points() if all_point_ids else _empty(),
        _get_standard_groups() if all_standard_group_ids else _empty(),
        _get_standards() if all_standard_ids else _empty(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    point_map = {p.id: str(p.value) if p.value is not None else "" for p in points_data}
    standard_group_map = {sg.id: sg.name for sg in standard_groups_data}
    standard_map = {s.id: s.name for s in standards_data}

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
        points_str = PIPE.join(point_map.get(pid, "") for pid in (a.point_ids or []))
        standard_groups_str = PIPE.join(
            standard_group_map.get(sgid, "") for sgid in (a.standard_group_ids or [])
        )
        standards_str = PIPE.join(
            standard_map.get(sid, "") for sid in (a.standard_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                points_str,
                standard_groups_str,
                standards_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"rubrics_export_{timestamp}.csv"

    return ExportRubricApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
