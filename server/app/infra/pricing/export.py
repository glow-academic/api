"""Pricing export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_runs — full dump (all runs, no filters, no pagination)
  3. compute_costs_from_runs — per-run cost computation
  4. get_names — hydrate agent/model names
  5. get_groups — hydrate group names
  6. ZIP generation (runs.csv) + upload entry creation
"""

from __future__ import annotations

import base64
import csv
import io
import zipfile
from datetime import datetime
from uuid import UUID

import asyncpg
from pydantic import BaseModel
from redis.asyncio import Redis

from app.infra.pricing import compute_costs_from_runs
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.groups.get import get_groups
from app.tools.entries.runs.search import search_runs
from app.tools.resources.names.get import get_names

PIPE = "|"

RUN_CSV_COLUMNS = [
    "run_id",
    "group",
    "run_date",
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "total_tokens",
    "cost",
    "agents",
    "models",
]


class ExportPricingApiResponse(BaseModel):
    """Response model for pricing export."""

    content: str
    file_name: str
    mime_type: str
    row_count: int


async def export_pricing_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
) -> dict:
    """Pricing full export using composable infra functions."""
    from fastapi import HTTPException

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all runs (full dump) --

    async with pool.acquire() as conn:
        runs, _total_count = await search_runs(conn, limit=100000, offset=0)

    if not runs:
        return ExportPricingApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Compute per-run costs --

    async with pool.acquire() as conn:
        run_costs = await compute_costs_from_runs(conn, runs)

    # -- Step 4: Hydrate names --

    all_agent_ids: set[UUID] = set()
    all_model_ids: set[UUID] = set()
    all_group_ids: set[UUID] = set()

    for r in runs:
        if r.agent_ids:
            all_agent_ids.update(r.agent_ids)
        if r.model_ids:
            all_model_ids.update(r.model_ids)
        if r.group_id:
            all_group_ids.add(r.group_id)

    all_name_ids = list(all_agent_ids | all_model_ids)
    async with pool.acquire() as conn:
        name_items = await get_names(conn, all_name_ids, redis) if all_name_ids else []
    name_map = {item.id: item.name for item in name_items if item.id and item.name}

    # Hydrate group names
    async with pool.acquire() as conn:
        groups = await get_groups(conn, list(all_group_ids)) if all_group_ids else []
    group_map = {g.id: g.name or "" for g in groups}

    # -- Step 5: Generate ZIP (runs.csv) + upload --

    runs_output = io.StringIO()
    runs_writer = csv.writer(runs_output)
    runs_writer.writerow(RUN_CSV_COLUMNS)

    for r in runs:
        total_tokens = r.input_tokens + r.output_tokens + r.cached_input_tokens
        cost = run_costs.get(r.run_id, 0)
        agents_str = PIPE.join(name_map.get(aid, "") for aid in (r.agent_ids or []))
        models_str = PIPE.join(name_map.get(mid, "") for mid in (r.model_ids or []))

        runs_writer.writerow(
            [
                str(r.run_id),
                group_map.get(r.group_id, "") if r.group_id else "",
                str(r.run_created_at) if r.run_created_at else "",
                str(r.input_tokens),
                str(r.output_tokens),
                str(r.cached_input_tokens),
                str(total_tokens),
                str(cost),
                agents_str,
                models_str,
            ]
        )

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("runs.csv", runs_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(runs)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"pricing_export_{timestamp}.zip"

    return ExportPricingApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
