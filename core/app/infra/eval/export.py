"""Eval export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_evals — full dump (all IDs, no filters, no pagination)
  3. get_evals — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, models, etc.)
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
from app.tools.artifacts.eval.get import get_evals
from app.tools.artifacts.eval.search import search_evals
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.models.get import get_models as get_models_resource
from app.tools.resources.names.get import get_names

PIPE = "|"

CSV_COLUMNS = [
    "eval_id",
    "name",
    "description",
    "active",
    "departments",
    "models",
]


async def export_eval_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    eval_id: UUID | None = None,
) -> dict:
    """Eval full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_evals → all IDs (full dump, no pagination)
      3. get_evals → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.eval.types import ExportEvalApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all evals (full dump) ────────────────────────

    if eval_id:
        eval_ids = [eval_id]
    else:
        async with pool.acquire() as conn:
            eval_ids, _total_count = await search_evals(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not eval_ids:
            return ExportEvalApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get eval artifacts with all junction IDs ────────────

    async with pool.acquire() as conn:
        artifacts = await get_evals(
            conn,
            eval_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            models=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_model_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_model_ids.extend(a.model_ids or [])

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

    async def _fetch_models() -> list:
        if not all_model_ids:
            return []
        async with pool.acquire() as conn:
            return await get_models_resource(conn, all_model_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        models_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_models(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    model_map = {m.id: m.name for m in models_data}

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
        models_str = PIPE.join(model_map.get(mid, "") for mid in (a.model_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                models_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"evals_export_{timestamp}.csv"

    return ExportEvalApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
