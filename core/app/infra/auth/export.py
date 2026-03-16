"""Auth export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_auths — full dump (all IDs, no filters, no pagination)
  3. get_auths — hydrate junction IDs
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
from app.tools.artifacts.auth.get import get_auths
from app.tools.artifacts.auth.search import search_auths
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.items.get import get_items
from app.tools.resources.names.get import get_names
from app.tools.resources.protocols.get import get_protocols
from app.tools.resources.slugs.get import get_slugs

PIPE = "|"

CSV_COLUMNS = [
    "auth_id",
    "name",
    "description",
    "active",
    "departments",
    "protocols",
    "slugs",
    "items",
]


async def export_auth_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    auth_id: UUID | None = None,
) -> dict:
    """Auth full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_auths -> all IDs (full dump, no pagination)
      3. get_auths -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.auth.types import ExportAuthApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all auths (full dump) --

    if auth_id:
        auth_ids = [auth_id]
    else:
        async with pool.acquire() as conn:
            auth_ids, _total_count = await search_auths(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not auth_ids:
            return ExportAuthApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # -- Step 3: Get auth artifacts with all junction IDs --

    async with pool.acquire() as conn:
        artifacts = await get_auths(
            conn,
            auth_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            items=True,
            protocols=True,
            slugs=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_item_ids: list[UUID] = []
    all_protocol_ids: list[UUID] = []
    all_slug_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_item_ids.extend(a.item_ids or [])
        all_protocol_ids.extend(a.protocol_ids or [])
        all_slug_ids.extend(a.slug_ids or [])

    async def _fetch_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as c:
            return await get_names(c, all_name_ids, redis)

    async def _fetch_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as c:
            return await get_descriptions(c, all_description_ids, redis)

    async def _fetch_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as c:
            return await get_departments(c, all_department_ids, redis)

    async def _fetch_items() -> list:
        if not all_item_ids:
            return []
        async with pool.acquire() as c:
            return await get_items(c, all_item_ids, redis)

    async def _fetch_protocols() -> list:
        if not all_protocol_ids:
            return []
        async with pool.acquire() as c:
            return await get_protocols(c, all_protocol_ids, redis)

    async def _fetch_slugs() -> list:
        if not all_slug_ids:
            return []
        async with pool.acquire() as c:
            return await get_slugs(c, all_slug_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        items_data,
        protocols_data,
        slugs_data,
    ) = await asyncio.gather(
        _fetch_names(),
        _fetch_descriptions(),
        _fetch_departments(),
        _fetch_items(),
        _fetch_protocols(),
        _fetch_slugs(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    item_map = {i.id: i.name for i in items_data}
    protocol_map = {p.id: p.value for p in protocols_data}
    slug_map = {s.id: s.value for s in slugs_data}

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
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        protocols_str = PIPE.join(
            protocol_map.get(pid, "") for pid in (a.protocol_ids or [])
        )
        slugs_str = PIPE.join(slug_map.get(sid, "") for sid in (a.slug_ids or []))
        items_str = PIPE.join(item_map.get(iid, "") for iid in (a.item_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                protocols_str,
                slugs_str,
                items_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"auths_export_{timestamp}.csv"

    return ExportAuthApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
