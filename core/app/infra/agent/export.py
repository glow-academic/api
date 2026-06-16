"""Agent export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_agents — full dump (all IDs, no filters, no pagination)
  3. get_agents — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, etc.)
  5. CSV generation + upload entry creation
"""

from __future__ import annotations

import asyncio
import io
import os
import uuid as uuid_mod
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.activate.activate import activate_rows
from app.infra.globals import UPLOAD_FOLDER
from app.infra.profile_identity_context import resolve_profile_identity_context
from app.infra.refresh.queue import enqueue_refreshes
from app.infra.server_timing import timed
from app.tools.artifacts.agent.get import get_agents
from app.tools.artifacts.agent.search import search_agents
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.resources.models.get import get_models
from app.tools.resources.names.get import get_names
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.tools.get import get_tools
from app.tools.resources.voices.get import get_voices
from app.utils.csv.formula_safe import FormulaSafeWriter
from app.utils.cache.hedged_row import transaction_with_writeback

PIPE = "|"

CSV_COLUMNS = [
    "agent_id",
    "name",
    "description",
    "active",
    "departments",
    "models",
    "reasoning_levels",
    "temperature_levels",
    "tools",
    "voices",
]


async def export_agent_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    agent_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> dict:
    """Agent full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_agents -> all IDs (full dump, no pagination)
      3. get_agents -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.agent.types import ExportAgentApiResponse

    # -- Step 1: Profile context --

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Short-circuit: ack path — promote/reject a staged export ──────────────
    # (mirrors persona/create; soft-call keyed by the server call_id which FKs
    # calls_entry, so the ack arrives with idempotency_key set to the echoed key.)
    if accept is not None and idempotency_key is not None:
        async with pool.acquire() as conn:
            entry = await get_soft_call(conn, idempotency_key, redis, artifact="agent")
        if entry is None or entry.status != "pending" or entry.operation != "export":
            raise HTTPException(
                status_code=404, detail="No pending export for this call.",
            )
        ids = entry.patch or {}
        if accept:
            async with pool.acquire() as conn:
                async with transaction_with_writeback(conn):
                    await activate_rows(conn, table="uploads_entry", ids=[UUID(ids["upload_id"])])
                    await activate_rows(conn, table="files_resource", ids=[UUID(ids["resource_id"])])
                    await activate_rows(conn, table="files_entry", ids=[UUID(ids["entry_id"])])
                    await activate_rows(conn, table="file_uploads_entry", ids=[UUID(ids["junction_id"])])
            await enqueue_refreshes(
                pool, redis, profile_id=profile_id, session_id=session_id,
                artifact_type="file", targets=["files_mv"], tags=["files"],
            )
        async with pool.acquire() as conn:
            await create_soft_call(
                conn, redis, call_id=idempotency_key, artifact="agent",
                operation="export", artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return ExportAgentApiResponse(
            file_id=entry.artifact_id,
            file_name=str(ids.get("file_name", "")),
            row_count=int(ids.get("row_count", 0)),
            idempotency_key=idempotency_key,
        )

    # -- Step 2: Search all agents (full dump) --

    if agent_id:
        agent_ids = [agent_id]
    else:
        with timed("search_agents"):
         async with pool.acquire() as conn:
            agent_ids, _total_count = await search_agents(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )


    # -- Step 3: Get agent artifacts with all junction IDs --

    with timed("get_agents"):
        artifacts = await get_agents(
            pool,
            agent_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            models=True,
            reasoning_levels=True,
            temperature_levels=True,
            tools=True,
            voices=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_model_ids: list[UUID] = []
    all_reasoning_level_ids: list[UUID] = []
    all_temperature_level_ids: list[UUID] = []
    all_tool_ids: list[UUID] = []
    all_voice_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_model_ids.extend(a.model_ids or [])
        all_reasoning_level_ids.extend(a.reasoning_level_ids or [])
        all_temperature_level_ids.extend(a.temperature_level_ids or [])
        all_tool_ids.extend(a.tool_ids or [])
        all_voice_ids.extend(a.voice_ids or [])

    async def _empty() -> list:
        return []

    async def _get_names() -> list:
        return await get_names(pool, all_name_ids, redis)

    async def _get_descriptions() -> list:
        return await get_descriptions(pool, all_description_ids, redis)

    async def _get_departments() -> list:
        return await get_departments(pool, all_department_ids, redis)

    async def _get_models() -> list:
        return await get_models(pool, all_model_ids, redis)

    async def _get_reasoning_levels() -> list:
        return await get_reasoning_levels(pool, all_reasoning_level_ids, redis)

    async def _get_temperature_levels() -> list:
        return await get_temperature_levels(pool, all_temperature_level_ids, redis)

    async def _get_tools() -> list:
        return await get_tools(pool, all_tool_ids, redis)

    async def _get_voices() -> list:
        return await get_voices(pool, all_voice_ids, redis)

    with timed("hydrate"):
     (
        names_data,
        descriptions_data,
        departments_data,
        models_data,
        reasoning_levels_data,
        temperature_levels_data,
        tools_data,
        voices_data,
     ) = await asyncio.gather(
        _get_names() if all_name_ids else _empty(),
        _get_descriptions() if all_description_ids else _empty(),
        _get_departments() if all_department_ids else _empty(),
        _get_models() if all_model_ids else _empty(),
        _get_reasoning_levels() if all_reasoning_level_ids else _empty(),
        _get_temperature_levels() if all_temperature_level_ids else _empty(),
        _get_tools() if all_tool_ids else _empty(),
        _get_voices() if all_voice_ids else _empty(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    model_map = {m.id: m.name for m in models_data}
    reasoning_level_map = {r.id: r.reasoning_level for r in reasoning_levels_data}
    temperature_level_map = {t.id: str(t.temperature) for t in temperature_levels_data}
    tool_map = {t.id: t.name for t in tools_data}
    voice_map = {v.id: v.voice for v in voices_data}

    # -- Step 5: Generate CSV + upload --

    with timed("csv_build"):
     output = io.StringIO()
     writer = FormulaSafeWriter(output)
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
        models_str = PIPE.join(model_map.get(mid, "") for mid in (a.model_ids or []))
        reasoning_levels_str = PIPE.join(
            reasoning_level_map.get(rid, "") for rid in (a.reasoning_level_ids or [])
        )
        temperature_levels_str = PIPE.join(
            temperature_level_map.get(tid, "")
            for tid in (a.temperature_level_ids or [])
        )
        tools_str = PIPE.join(tool_map.get(tid, "") for tid in (a.tool_ids or []))
        voices_str = PIPE.join(voice_map.get(vid, "") for vid in (a.voice_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                models_str,
                reasoning_levels_str,
                temperature_levels_str,
                tools_str,
                voices_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    csv_bytes = csv_content.encode("utf-8")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"agents_export_{timestamp}.csv"
    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.csv"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(csv_bytes)

    with timed("db_write"):
     async with pool.acquire() as conn:
        upload_row = await create_upload(
            conn,
            redis, session_id=session_id,
            file_path=relative_path,
            mime_type="text/csv",
            size=len(csv_bytes),
            soft=soft,
        )
        resource_row = await create_file_resource(conn, redis, soft=soft)
        if session_id is not None:
            entry_row = await create_file_entry(
                conn,
                redis,
                session_id=session_id,
                files_id=resource_row.id,
                soft=soft,
            )
            junction_row = await create_file_upload(
                conn,
                redis, file_id=entry_row.id,
                upload_id=upload_row.id,
                session_id=session_id,
                soft=soft,
            )
            if soft and call_id is not None:
                await create_soft_call(
                    conn,
                    redis,
                    call_id=call_id,
                    artifact="agent",
                    operation="export",
                    artifact_id=resource_row.id,
                    status="pending",
                    patch={
                        "upload_id": str(upload_row.id),
                        "resource_id": str(resource_row.id),
                        "entry_id": str(entry_row.id),
                        "junction_id": str(junction_row.id),
                        "file_name": file_name,
                        "row_count": row_count,
                    },
                )

    await enqueue_refreshes(
        pool, redis, profile_id=profile_id, session_id=session_id,
        artifact_type="file", targets=["files_mv"], tags=["files"],
    )

    return ExportAgentApiResponse(
        file_id=resource_row.id,
        file_name=file_name,
        row_count=row_count,
        idempotency_key=call_id,
    )
