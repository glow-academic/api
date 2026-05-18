"""Department export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_departments — full dump (all IDs, no filters, no pagination)
  3. get_departments (artifact) — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, settings)
  5. CSV generation + upload entry creation
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import uuid as uuid_mod
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.globals import UPLOAD_FOLDER

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.files.refresh import refresh_files_internal
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.artifacts.department.get import (
    get_departments as get_department_artifacts,
)
from app.tools.artifacts.department.search import search_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.names.get import get_names
from app.tools.resources.settings.get import get_settings

PIPE = "|"

CSV_COLUMNS = [
    "department_id",
    "name",
    "description",
    "active",
    "settings",
]


async def export_department_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    department_id: UUID | None = None,
) -> dict:
    """Department full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_departments -> all IDs (full dump, no pagination)
      3. get_departments (artifact) -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.department.types import ExportDepartmentApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all departments (full dump) --

    if department_id:
        department_ids = [department_id]
    else:
        async with pool.acquire() as conn:
            department_ids, _total_count = await search_departments(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )


    # -- Step 3: Get department artifacts with all junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_department_artifacts(
            conn,
            department_ids,
            names=True,
            descriptions=True,
            flags=True,
            settings=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_settings_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_settings_ids.extend(a.settings_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        return await get_descriptions(pool, all_description_ids, redis)

    async def _fetch_settings() -> list:
        if not all_settings_ids:
            return []
        return await get_settings(pool, all_settings_ids, redis)

    (
        names_data,
        descriptions_data,
        settings_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_settings(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    setting_map = {s.id: s.name for s in settings_data}

    # -- Step 5: Generate CSV + upload --

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
        settings_str = PIPE.join(
            setting_map.get(sid, "") for sid in (a.settings_ids or [])
        )

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                settings_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    csv_bytes = csv_content.encode("utf-8")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"departments_export_{timestamp}.csv"
    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.csv"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(csv_bytes)

    async with pool.acquire() as conn:
        upload_row = await create_upload(
            conn,
            session_id=session_id,
            file_path=relative_path,
            mime_type="text/csv",
            size=len(csv_bytes),
        )
        resource_row = await create_file_resource(conn, redis)
        if session_id is not None:
            entry_row = await create_file_entry(
                conn,
                session_id=session_id,
                files_id=resource_row.id,
            )
            await create_file_upload(
                conn,
                file_id=entry_row.id,
                upload_id=upload_row.id,
                session_id=session_id,
            )
            await refresh_files_internal(conn, redis)

    return ExportDepartmentApiResponse(
        file_id=resource_row.id,
        file_name=file_name,
        row_count=row_count,
    )
