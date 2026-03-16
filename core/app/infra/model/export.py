"""Model export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_models — full dump (all IDs, no filters, no pagination)
  3. get_models — hydrate junction IDs
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
from app.tools.artifacts.model.get import get_models
from app.tools.artifacts.model.search import search_models
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.modalities.get import get_modalities
from app.tools.resources.names.get import get_names
from app.tools.resources.providers.get import get_providers
from app.tools.resources.qualities.get import get_qualities
from app.tools.resources.reasoning_levels.get import get_reasoning_levels
from app.tools.resources.temperature_levels.get import get_temperature_levels
from app.tools.resources.values.get import get_values
from app.tools.resources.voices.get import get_voices

PIPE = "|"

CSV_COLUMNS = [
    "model_id",
    "name",
    "description",
    "active",
    "departments",
    "value",
    "provider",
    "modalities",
    "temperature_levels",
    "reasoning_levels",
    "qualities",
    "voices",
]


async def export_model_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    model_id: UUID | None = None,
) -> dict:
    """Model full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_models → all IDs (full dump, no pagination)
      3. get_models → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.model.types import ExportModelApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all models (full dump) ────────────────────────

    if model_id:
        model_ids = [model_id]
    else:
        async with pool.acquire() as conn:
            model_ids, _total_count = await search_models(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

        if not model_ids:
            return ExportModelApiResponse(
                content="",
                file_name="",
                mime_type="text/csv",
                row_count=0,
            )

    # ── Step 3: Get model artifacts with all junction IDs ────────────

    async with pool.acquire() as conn:
        artifacts = await get_models(
            conn,
            model_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            values=True,
            providers=True,
            modalities=True,
            temperature_levels=True,
            reasoning_levels=True,
            qualities=True,
            voices=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_value_ids: list[UUID] = []
    all_provider_ids: list[UUID] = []
    all_modality_ids: list[UUID] = []
    all_temperature_level_ids: list[UUID] = []
    all_reasoning_level_ids: list[UUID] = []
    all_quality_ids: list[UUID] = []
    all_voice_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_value_ids.extend(a.value_ids or [])
        all_provider_ids.extend(a.provider_ids or [])
        all_modality_ids.extend(a.modality_ids or [])
        all_temperature_level_ids.extend(a.temperature_level_ids or [])
        all_reasoning_level_ids.extend(a.reasoning_level_ids or [])
        all_quality_ids.extend(a.quality_ids or [])
        all_voice_ids.extend(a.voice_ids or [])

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

    async def _fetch_values() -> list:
        async with pool.acquire() as conn:
            return await get_values(conn, all_value_ids, redis)

    async def _fetch_providers() -> list:
        async with pool.acquire() as conn:
            return await get_providers(conn, all_provider_ids, redis)

    async def _fetch_modalities() -> list:
        async with pool.acquire() as conn:
            return await get_modalities(conn, all_modality_ids, redis)

    async def _fetch_temperature_levels() -> list:
        async with pool.acquire() as conn:
            return await get_temperature_levels(conn, all_temperature_level_ids, redis)

    async def _fetch_reasoning_levels() -> list:
        async with pool.acquire() as conn:
            return await get_reasoning_levels(conn, all_reasoning_level_ids, redis)

    async def _fetch_qualities() -> list:
        async with pool.acquire() as conn:
            return await get_qualities(conn, all_quality_ids, redis)

    async def _fetch_voices() -> list:
        async with pool.acquire() as conn:
            return await get_voices(conn, all_voice_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        values_data,
        providers_data,
        modalities_data,
        temperature_levels_data,
        reasoning_levels_data,
        qualities_data,
        voices_data,
    ) = await asyncio.gather(
        _fetch_names() if all_name_ids else _empty(),
        _fetch_descriptions() if all_description_ids else _empty(),
        _fetch_departments() if all_department_ids else _empty(),
        _fetch_values() if all_value_ids else _empty(),
        _fetch_providers() if all_provider_ids else _empty(),
        _fetch_modalities() if all_modality_ids else _empty(),
        _fetch_temperature_levels() if all_temperature_level_ids else _empty(),
        _fetch_reasoning_levels() if all_reasoning_level_ids else _empty(),
        _fetch_qualities() if all_quality_ids else _empty(),
        _fetch_voices() if all_voice_ids else _empty(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    value_map = {v.id: v.value for v in values_data}
    provider_map = {p.id: p.name for p in providers_data}
    modality_map = {m.id: m.modality for m in modalities_data}
    temperature_level_map = {t.id: str(t.temperature) for t in temperature_levels_data}
    reasoning_level_map = {r.id: r.reasoning_level for r in reasoning_levels_data}
    quality_map = {q.id: q.quality for q in qualities_data}
    voice_map = {v.id: v.voice for v in voices_data}

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
        value = value_map.get(a.value_ids[0], "") if a.value_ids else ""
        provider = provider_map.get(a.provider_ids[0], "") if a.provider_ids else ""
        modalities_str = PIPE.join(
            modality_map.get(mid, "") for mid in (a.modality_ids or [])
        )
        temperature_levels_str = PIPE.join(
            temperature_level_map.get(tid, "")
            for tid in (a.temperature_level_ids or [])
        )
        reasoning_levels_str = PIPE.join(
            reasoning_level_map.get(rid, "") for rid in (a.reasoning_level_ids or [])
        )
        qualities_str = PIPE.join(
            quality_map.get(qid, "") for qid in (a.quality_ids or [])
        )
        voices_str = PIPE.join(voice_map.get(vid, "") for vid in (a.voice_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                active,
                departments_str,
                value,
                provider,
                modalities_str,
                temperature_levels_str,
                reasoning_levels_str,
                qualities_str,
                voices_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"models_export_{timestamp}.csv"

    return ExportModelApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
