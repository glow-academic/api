"""Persona export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_personas — full dump (all IDs, no filters, no pagination)
  3. get_personas — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, colors, etc.)
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
from app.infra.server_timing import timed
from app.tools.artifacts.persona.get import get_personas
from app.tools.artifacts.persona.search import search_personas
from app.tools.entries.file_uploads.create import create_file_upload
from app.tools.entries.files.create import create_file as create_file_entry
from app.infra.refresh.queue import enqueue_refreshes
from app.tools.entries.uploads.create import create_upload
from app.tools.resources.colors.get import get_colors
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.examples.get import get_examples
from app.tools.resources.fields.get import get_fields
from app.tools.resources.files.create import create_file as create_file_resource
from app.tools.resources.icons.get import get_icons
from app.tools.resources.instructions.get import get_instructions
from app.tools.resources.names.get import get_names
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.voices.get import get_voices

PIPE = "|"

CSV_COLUMNS = [
    "persona_id",
    "name",
    "description",
    "color",
    "icon",
    "instructions",
    "active",
    "departments",
    "examples",
    "parameter_fields",
    "voices",
]


async def export_persona_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    session_id: UUID | None = None,
    id: UUID | None = None,
    **_kwargs,
) -> dict:
    """Persona full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context → role, department_ids
      2. search_personas → all IDs (full dump, no pagination)
      3. get_personas → junction IDs per artifact
      4. Parallel resource hydration → human-readable values
      5. Write CSV to disk; create uploads_entry + files_resource +
         file_uploads_entry junction; return ``file_id``. Client
         downloads via ``/persona/file/download`` (BFF wrap at
         ``/api/persona/download/{file_id}``).
    """
    persona_id = id  # alias: tools send 'id', internal code uses 'persona_id'
    from fastapi import HTTPException

    from app.infra.persona.types import ExportPersonaApiResponse

    # ── Step 1: Profile context ────────────────────────────────────────

    with timed("profile"):
        profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # ── Step 2: Search all personas (full dump) ────────────────────────

    with timed("query"):
      async with pool.acquire() as conn:
        if persona_id:
            persona_ids = [persona_id]
        else:
            persona_ids, _total_count = await search_personas(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )
            # Empty result is fine — falls through to the upload path
            # below and produces a header-only CSV uploaded as a real
            # file_id, so the client download flow stays uniform.

        # ── Step 3: Get persona artifacts with all junction IDs ────────────

        artifacts = await get_personas(
            conn,
            persona_ids,
            names=True,
            descriptions=True,
            colors=True,
            icons=True,
            departments=True,
            flags=True,
            instructions=True,
            examples=True,
            parameter_fields=True,
            voices=True,
        )

    # ── Step 4: Parallel resource hydration ────────────────────────────

    # Collect all resource IDs across artifacts
    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_color_ids: list[UUID] = []
    all_icon_ids: list[UUID] = []
    all_instruction_ids: list[UUID] = []
    all_example_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_parameter_field_ids: list[UUID] = []
    all_voice_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_color_ids.extend(a.color_ids or [])
        all_icon_ids.extend(a.icon_ids or [])
        all_instruction_ids.extend(a.instruction_ids or [])
        all_example_ids.extend(a.example_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_parameter_field_ids.extend(a.parameter_field_ids or [])
        all_voice_ids.extend(a.voice_ids or [])

    # Each branch acquires its own connection from the pool.

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        return await get_names(pool, all_name_ids, redis)

    async def _get_descriptions() -> list:
        if not all_description_ids:
            return []
        return await get_descriptions(pool, all_description_ids, redis)

    async def _get_colors() -> list:
        if not all_color_ids:
            return []
        return await get_colors(pool, all_color_ids, redis)

    async def _get_icons() -> list:
        if not all_icon_ids:
            return []
        return await get_icons(pool, all_icon_ids, redis)

    async def _get_instructions() -> list:
        if not all_instruction_ids:
            return []
        return await get_instructions(pool, all_instruction_ids, redis)

    async def _get_examples() -> list:
        if not all_example_ids:
            return []
        return await get_examples(pool, all_example_ids, redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        return await get_departments(pool, all_department_ids, redis)

    async def _get_parameter_fields() -> list:
        if not all_parameter_field_ids:
            return []
        return await get_parameter_fields(pool, all_parameter_field_ids, redis)

    async def _get_voices() -> list:
        if not all_voice_ids:
            return []
        return await get_voices(pool, all_voice_ids, redis)

    with timed("hydrate"):
        (
            names_data,
            descriptions_data,
            colors_data,
            icons_data,
            instructions_data,
            examples_data,
            departments_data,
            parameter_fields_data,
            voices_data,
        ) = await asyncio.gather(
            _get_names(),
            _get_descriptions(),
            _get_colors(),
            _get_icons(),
            _get_instructions(),
            _get_examples(),
            _get_departments(),
            _get_parameter_fields(),
            _get_voices(),
        )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    color_map = {c.id: c.name for c in colors_data}
    icon_map = {i.id: i.name for i in icons_data}
    instruction_map = {i.id: i.template for i in instructions_data}
    example_map = {e.id: e.example for e in examples_data}
    department_map = {d.id: d.name for d in departments_data}
    voice_map = {v.id: v.voice for v in voices_data}

    # Parameter fields: two-hop (parameter_field → field → name)
    pf_field_id_map = {pf.id: pf.field_id for pf in parameter_fields_data}
    all_field_ids = list({fid for fid in pf_field_id_map.values() if fid})
    if all_field_ids:
        fields_data = await get_fields(pool, all_field_ids, redis)
    else:
        fields_data = []
    field_name_map = {f.id: f.name for f in fields_data}
    # pf_id → human-readable field name
    pf_name_map = {
        pf_id: field_name_map.get(field_id, "")
        for pf_id, field_id in pf_field_id_map.items()
        if field_id
    }

    # ── Step 5: Generate CSV + upload ──────────────────────────────────

    with timed("build_csv"):
      output = io.StringIO()
      writer = csv.writer(output)
      writer.writerow(CSV_COLUMNS)

      for a in artifacts:
        # Single-select: first resource value
        name = name_map.get(a.name_ids[0], "") if a.name_ids else ""
        description = (
            description_map.get(a.description_ids[0], "") if a.description_ids else ""
        )
        color = color_map.get(a.color_ids[0], "") if a.color_ids else ""
        icon = icon_map.get(a.icon_ids[0], "") if a.icon_ids else ""
        instructions = (
            instruction_map.get(a.instruction_ids[0], "") if a.instruction_ids else ""
        )

        # Active flag
        active = "Yes" if a.active else "No"

        # Multi-select: pipe-delimited values
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        examples_str = PIPE.join(
            example_map.get(eid, "") for eid in (a.example_ids or [])
        )
        pf_str = PIPE.join(
            pf_name_map.get(pfid, "") for pfid in (a.parameter_field_ids or [])
        )
        voices_str = PIPE.join(voice_map.get(vid, "") for vid in (a.voice_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                color,
                icon,
                instructions,
                active,
                departments_str,
                examples_str,
                pf_str,
                voices_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)
    csv_bytes = csv_content.encode("utf-8")

    # ── Step 5: Write CSV to disk + register as a file resource ────────
    # File modality: every export becomes a real ``files_resource`` row
    # backed by an ``uploads_entry`` on disk. The client downloads via
    # ``/persona/file/download`` (or the BFF wrap at
    # ``/api/persona/download/{file_id}``) — same path PDF/other-mime
    # exports will use later.
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"personas_export_{timestamp}.csv"
    upload_uuid = uuid_mod.uuid4()
    relative_path = f"{upload_uuid}.csv"
    disk_path = os.path.join(UPLOAD_FOLDER, relative_path)
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    with open(disk_path, "wb") as f:
        f.write(csv_bytes)

    # Canonical 4-step chain (mirrors ``create_document_file``):
    #   upload (file on disk + entry)
    #   → files_resource (the catalog id the client downloads by — this
    #     is the value returned as ``file_id``; matches the ``files_ids``
    #     filter used in ``file_download_persona_impl``)
    #   → files_entry (the instance, linked to the resource via
    #     file_files_connection) — needed because ``file_uploads_entry``
    #     FKs to ``files_entry``, not ``files_resource``
    #   → file_uploads junction (entry.id ↔ upload.id)
    with timed("upload"):
        async with pool.acquire() as conn:
            upload_row = await create_upload(
                conn,
                redis, session_id=session_id,
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
                    redis, file_id=entry_row.id,
                    upload_id=upload_row.id,
                    session_id=session_id,
                )
    # Enqueue async files_mv refresh via the MV worker. The client's
    # follow-up download will retry briefly if it loses the race; this
    # path is rare enough that we accept the trade-off vs. blocking the
    # request 50–200ms.
    with timed("refresh"):
        await enqueue_refreshes(
            pool, redis, profile_id=profile_id, session_id=session_id,
            artifact_type="file", targets=["files_mv"], tags=["files"],
        )

    return ExportPersonaApiResponse(
        file_id=resource_row.id,
        file_name=file_name,
        row_count=row_count,
    )
