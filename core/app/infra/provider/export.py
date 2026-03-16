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
import base64
import csv
import io
from datetime import datetime
from uuid import UUID

import asyncpg
from redis.asyncio import Redis

from app.infra.profile_identity_context import resolve_profile_identity_context
from app.tools.artifacts.provider.get import get_providers
from app.tools.artifacts.provider.search import search_providers
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.endpoints.get import get_endpoints
from app.tools.resources.keys.get import get_keys
from app.tools.resources.names.get import get_names
from app.tools.resources.values.get import get_values

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
    provider_id: UUID | None = None,
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

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all providers (full dump) ─────────────────────

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

            if not provider_ids:
                return ExportProviderApiResponse(
                    content="",
                    file_name="",
                    mime_type="text/csv",
                    row_count=0,
                )

    # ── Step 3: Get provider artifacts with all junction IDs ─────────

    async with pool.acquire() as conn:
        artifacts = await get_providers(
            conn,
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
        all_value_ids.extend(a.value_ids or [])

    async def _empty() -> list:
        return []

    async def _fetch_names() -> list:
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _fetch_departments() -> list:
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _fetch_endpoints() -> list:
        async with pool.acquire() as conn:
            return await get_endpoints(conn, all_endpoint_ids, redis)

    async def _fetch_keys() -> list:
        async with pool.acquire() as conn:
            return await get_keys(conn, all_key_ids, redis)

    async def _fetch_values() -> list:
        async with pool.acquire() as conn:
            return await get_values(conn, all_value_ids, redis)

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
        endpoints_str = PIPE.join(
            endpoint_map.get(eid, "") for eid in (a.endpoint_ids or [])
        )
        keys_str = PIPE.join(key_map.get(kid, "") for kid in (a.key_ids or []))
        values_str = PIPE.join(value_map.get(vid, "") for vid in (a.value_ids or []))

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

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"providers_export_{timestamp}.csv"

    return ExportProviderApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
