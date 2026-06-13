"""Provider export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_providers — full dump (all IDs, no filters, no pagination)
  3. get_providers — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, departments, endpoints, keys, values)
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
from app.tools.artifacts.provider.get import get_providers
from app.tools.artifacts.provider.search import search_providers
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.tools.entries.soft_calls.create import create_soft_call
from app.tools.entries.soft_calls.get import get_soft_call
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.resources.keys.get import get_keys
from app.tools.resources.names.get import get_names
from app.tools.resources.values.get import get_values
from app.utils.csv.formula_safe import FormulaSafeWriter

PIPE = "|"

CSV_COLUMNS = [
    "provider_id",
    "name",
    "description",
    "active",
    "departments",
    "endpoints",
    "keys",
    "values",
]


async def export_provider_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    provider_id: UUID | None = None,
    soft: bool = False,
    accept: bool | None = None,
    idempotency_key: UUID | None = None,
    call_id: UUID | None = None,
) -> dict:
    """Provider full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_providers → all IDs (full dump, no pagination)
      3. get_providers → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.provider.types import ExportProviderApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

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
            entry = await get_soft_call(conn, idempotency_key, redis, artifact="provider")
        if entry is None or entry.status != "pending" or entry.operation != "export":
            raise HTTPException(
                status_code=404, detail="No pending export for this call.",
            )
        ids = entry.patch or {}
        if accept:
            async with pool.acquire() as conn:
                async with conn.transaction():
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
                conn, redis, call_id=idempotency_key, artifact="provider",
                operation="export", artifact_id=entry.artifact_id,
                status="accepted" if accept else "rejected",
            )
        return ExportProviderApiResponse(
            file_id=entry.artifact_id,
            file_name=str(ids.get("file_name", "")),
            row_count=int(ids.get("row_count", 0)),
            idempotency_key=idempotency_key,
        )

    # ── Step 2: Search all providers (full dump) ─────────────────────

    with timed("query"):
     async with pool.acquire() as conn:
        if provider_id:
            provider_ids = [provider_id]
        else:
            provider_ids, _total_count = await search_providers(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )


    # ── Step 3: Get provider artifacts with all junction IDs ─────────

    with timed("hydrate"):
     artifacts = await get_providers(
        pool,
        provider_ids,
        names=True,
        descriptions=True,
        departments=True,
        flags=True,
        endpoints=True,
        keys=True,
        values=True,
    )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    # Collect all resource IDs across artifacts
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_endpoint_ids: list[UUID] = []
    all_key_ids: list[UUID] = []
    all_value_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_endpoint_ids.extend(a.endpoint_ids or [])
        all_key_ids.extend(a.key_ids or [])
        if a.value_id:
            all_value_ids.append(a.value_id)

    async def _empty() -> list:
        return []

    async def _fetch_names() -> list:
        return await get_names(pool, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        return await get_descriptions(pool, all_description_ids, redis)

    async def _fetch_departments() -> list:
        return await get_departments(pool, all_department_ids, redis)

    async def _fetch_endpoints() -> list:
        return await get_endpoints(pool, all_endpoint_ids, redis)

    async def _fetch_keys() -> list:
        return await get_keys(pool, all_key_ids, redis)

    async def _fetch_values() -> list:
        return await get_values(pool, all_value_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        endpoints_data,
        keys_data,
        values_data,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty(),
        _fetch_descriptions() if all_description_ids else _empty(),
        _fetch_departments() if all_department_ids else _empty(),
        _fetch_endpoints() if all_endpoint_ids else _empty(),
        _fetch_keys() if all_key_ids else _empty(),
        _fetch_values() if all_value_ids else _empty(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    endpoint_map = {e.id: e.base_url for e in endpoints_data}
    key_map = {k.id: k.name for k in keys_data}
    value_map = {v.id: v.value for v in values_data}

    # ── Step 5: Generate CSV + upload ──────────────────────────────────

    with timed("build_csv"):
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
        endpoints_str = PIPE.join(
            endpoint_map.get(eid, "") for eid in (a.endpoint_ids or [])
        )
        keys_str = PIPE.join(key_map.get(kid, "") for kid in (a.key_ids or []))
        values_str = value_map.get(a.value_id, "") if a.value_id else ""

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                endpoints_str,
                keys_str,
                values_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    with timed("upload"):
     csv_bytes = csv_content.encode("utf-8")
     timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
     file_name = f"providers_export_{timestamp}.csv"
     upload_uuid = uuid_mod.uuid4()
     relative_path = f"{upload_uuid}.csv"
     disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
     os.makedirs(UPLOAD_FOLDER, exist_ok=True)
     with open(disk_path, "wb") as f:
         f.write(csv_bytes)

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
                    artifact="provider",
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

    with timed("refresh"):
        await enqueue_refreshes(
            pool, redis, profile_id=profile_id, session_id=session_id,
            artifact_type="file", targets=["files_mv"], tags=["files"],
        )

    return ExportProviderApiResponse(
        file_id=resource_row.id,
        file_name=file_name,
        row_count=row_count,
        idempotency_key=call_id,
    )
