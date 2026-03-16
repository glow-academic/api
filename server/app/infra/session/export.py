"""Session export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. get_sessions — session metadata by ID
  3. search_groups — all groups for this session
  4. search_runs — all runs for all groups
  5. compute_costs_from_runs — per-run cost computation
  6. get_names — hydrate agent/model names
  7. get_profiles — hydrate profile names
  8. ZIP generation (sessions.csv + groups.csv + runs.csv) + upload entry creation
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import zipfile
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.pricing import compute_costs_from_runs
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.groups.search import search_groups
from app.tools.entries.runs.search import search_runs
from app.tools.entries.sessions.get import get_sessions
from app.tools.resources.names.get import get_names
from app.tools.resources.profiles.get import get_profiles

PIPE = "|"

SESSION_CSV_COLUMNS = [
    "session_id",
    "profile",
    "created_at",
    "active",
    "mcp",
]

GROUP_CSV_COLUMNS = [
    "group_id",
    "session_id",
    "group_name",
    "created_at",
    "active",
    "mcp",
]

RUN_CSV_COLUMNS = [
    "run_id",
    "group_id",
    "run_date",
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "agents",
    "models",
    "cost",
]


async def export_session_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    target_session_id: UUID,
) -> dict:
    """Session export using composable infra functions."""
    from fastapi import HTTPException

    from app.infra.session.types import ExportSessionApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Get session metadata --

    async with pool.acquire() as conn:
        sessions = await get_sessions(conn, [target_session_id])

    if not sessions:
        return ExportSessionApiResponse(
            content="",
            file_name="",
            mime_type="application/zip",
            row_count=0,
        )

    # -- Step 3: Get groups for this session --

    async with pool.acquire() as conn:
        groups = await search_groups(
            conn, session_ids=[target_session_id], limit=100000, offset=0
        )

    # -- Step 4: Get runs for all groups --

    all_group_ids = [g.id for g in groups]
    if all_group_ids:
        async with pool.acquire() as conn:
            runs = (
                await search_runs(conn, group_ids=all_group_ids, limit=100000, offset=0)
            )[0]
    else:
        runs = []

    # -- Step 5: Compute per-run costs --

    if runs:
        async with pool.acquire() as conn:
            run_costs = await compute_costs_from_runs(conn, runs)
    else:
        run_costs = {}

    # -- Step 6: Hydrate names --

    all_profile_ids: set[UUID] = set()
    all_agent_ids: set[UUID] = set()
    all_model_ids: set[UUID] = set()

    for s in sessions:
        if s.profile_id:
            all_profile_ids.add(s.profile_id)

    for r in runs:
        if r.agent_ids:
            all_agent_ids.update(r.agent_ids)
        if r.model_ids:
            all_model_ids.update(r.model_ids)

    all_name_ids = list(all_agent_ids | all_model_ids)

    async def _fetch_profiles() -> list:
        if not all_profile_ids:
            return []
        async with pool.acquire() as c:
            return await get_profiles(c, list(all_profile_ids), redis)

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as c:
            return await get_names(c, all_name_ids, redis)

    profiles_data, name_items = await asyncio.gather(
        _fetch_profiles(),
        _fetch_names(),
    )

    profile_map = {p.id: p.name or "" for p in profiles_data}
    name_map = {item.id: item.name for item in name_items if item.id and item.name}

    # -- Step 7: Generate ZIP (sessions.csv + groups.csv + runs.csv) + upload --

    # Generate sessions CSV
    sessions_output = io.StringIO()
    sessions_writer = csv.writer(sessions_output)
    sessions_writer.writerow(SESSION_CSV_COLUMNS)

    for s in sessions:
        sessions_writer.writerow(
            [
                str(s.id),
                profile_map.get(s.profile_id, "") if s.profile_id else "",
                str(s.created_at) if s.created_at else "",
                "Yes" if s.active else "No",
                "Yes" if s.mcp else "No",
            ]
        )

    # Generate groups CSV
    groups_output = io.StringIO()
    groups_writer = csv.writer(groups_output)
    groups_writer.writerow(GROUP_CSV_COLUMNS)

    for g in groups:
        groups_writer.writerow(
            [
                str(g.id),
                str(g.session_id) if g.session_id else "",
                g.name or "",
                str(g.created_at) if g.created_at else "",
                "Yes" if g.active else "No",
                "Yes" if g.mcp else "No",
            ]
        )

    # Generate runs CSV
    runs_output = io.StringIO()
    runs_writer = csv.writer(runs_output)
    runs_writer.writerow(RUN_CSV_COLUMNS)

    for r in runs:
        cost = run_costs.get(r.run_id, 0)
        agents_str = PIPE.join(name_map.get(aid, "") for aid in (r.agent_ids or []))
        models_str = PIPE.join(name_map.get(mid, "") for mid in (r.model_ids or []))

        runs_writer.writerow(
            [
                str(r.run_id),
                str(r.group_id) if r.group_id else "",
                str(r.run_created_at) if r.run_created_at else "",
                str(r.input_tokens),
                str(r.output_tokens),
                str(r.cached_input_tokens),
                agents_str,
                models_str,
                str(cost),
            ]
        )

    # Create ZIP
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("sessions.csv", sessions_output.getvalue())
        zf.writestr("groups.csv", groups_output.getvalue())
        zf.writestr("runs.csv", runs_output.getvalue())

    zip_content = zip_buffer.getvalue()
    row_count = len(sessions) + len(groups) + len(runs)

    content = base64.b64encode(zip_content).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"session_export_{timestamp}.zip"

    return ExportSessionApiResponse(
        content=content,
        file_name=file_name,
        mime_type="application/zip",
        row_count=row_count,
    )
