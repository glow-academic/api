"""Scenario export logic — composable infra architecture.

Composes existing black-box tools:
  1. resolve_profile_identity_context — profile (role, departments)
  2. search_scenarios — full dump (all IDs, no filters, no pagination)
  3. get_scenarios — hydrate junction IDs
  4. Resource get tools — parallel hydration (names, descriptions, etc.)
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
from app.tools.artifacts.scenario.get import get_scenarios
from app.tools.artifacts.scenario.search import search_scenarios
from app.tools.resources.departments.get import get_departments
from app.tools.resources.descriptions.get import get_descriptions
from app.tools.resources.documents.get import get_documents
from app.tools.resources.fields.get import get_fields
from app.tools.resources.images.get import get_images
from app.tools.resources.names.get import get_names
from app.tools.resources.objectives.get import get_objectives
from app.tools.resources.options.get import get_options
from app.tools.resources.parameter_fields.get import get_parameter_fields
from app.tools.resources.personas.get import get_personas
from app.tools.resources.problem_statements.get import get_problem_statements
from app.tools.resources.questions.get import get_questions
from app.tools.resources.videos.get import get_videos

PIPE = "|"

CSV_COLUMNS = [
    "scenario_id",
    "name",
    "description",
    "problem_statement",
    "active",
    "departments",
    "personas",
    "documents",
    "parameter_fields",
    "objectives",
    "images",
    "videos",
    "questions",
    "options",
]


async def export_scenario_impl(
    pool: asyncpg.Pool,
    redis: Redis,
    *,
    profile_id: UUID,
    scenario_id: UUID | None = None,
) -> dict:
    """Scenario full export using composable infra functions.

    Flow:
      1. resolve_profile_identity_context -> role, department_ids
      2. search_scenarios -> all IDs (full dump, no pagination)
      3. get_scenarios -> junction IDs per artifact
      4. Parallel resource hydration -> human-readable values
      5. Generate CSV + create upload entry
    """
    from fastapi import HTTPException

    from app.infra.scenario.types import ExportScenarioApiResponse

    # -- Step 1: Profile context --

    profile = await resolve_profile_identity_context(pool, profile_id, redis)

    if profile is None:
        raise HTTPException(
            status_code=401,
            detail="Profile not found. Please sign in again.",
        )

    # -- Step 2: Search all scenarios (full dump) --

    async with pool.acquire() as conn:
        if scenario_id:
            scenario_ids = [scenario_id]
        else:
            scenario_ids, _total_count = await search_scenarios(
                conn,
                active_only=False,
                limit_count=100000,
                offset_count=0,
            )

            if not scenario_ids:
                return ExportScenarioApiResponse(
                    content="",
                    file_name="",
                    mime_type="text/csv",
                    row_count=0,
                )

        # -- Step 3: Get scenario artifacts with all junction IDs --

        artifacts = await get_scenarios(
            conn,
            scenario_ids,
            names=True,
            descriptions=True,
            departments=True,
            flags=True,
            documents=True,
            images=True,
            objectives=True,
            options=True,
            parameter_fields=True,
            personas=True,
            problem_statements=True,
            questions=True,
            videos=True,
        )

    # -- Step 4: Parallel resource hydration --

    all_name_ids: list[UUID] = []
    all_description_ids: list[UUID] = []
    all_department_ids: list[UUID] = []
    all_document_ids: list[UUID] = []
    all_image_ids: list[UUID] = []
    all_objective_ids: list[UUID] = []
    all_option_ids: list[UUID] = []
    all_parameter_field_ids: list[UUID] = []
    all_persona_ids: list[UUID] = []
    all_problem_statement_ids: list[UUID] = []
    all_question_ids: list[UUID] = []
    all_video_ids: list[UUID] = []

    for a in artifacts:
        all_name_ids.extend(a.name_ids or [])
        all_description_ids.extend(a.description_ids or [])
        all_department_ids.extend(a.department_ids or [])
        all_document_ids.extend(a.document_ids or [])
        all_image_ids.extend(a.image_ids or [])
        all_objective_ids.extend(a.objective_ids or [])
        all_option_ids.extend(a.option_ids or [])
        all_parameter_field_ids.extend(a.parameter_field_ids or [])
        all_persona_ids.extend(a.persona_ids or [])
        all_problem_statement_ids.extend(a.problem_statement_ids or [])
        all_question_ids.extend(a.question_ids or [])
        all_video_ids.extend(a.video_ids or [])

    # Each branch acquires its own connection from the pool.

    async def _get_names() -> list:
        if not all_name_ids:
            return []
        async with pool.acquire() as conn:
            return await get_names(conn, all_name_ids, redis)

    async def _get_descriptions() -> list:
        if not all_description_ids:
            return []
        async with pool.acquire() as conn:
            return await get_descriptions(conn, all_description_ids, redis)

    async def _get_departments() -> list:
        if not all_department_ids:
            return []
        async with pool.acquire() as conn:
            return await get_departments(conn, all_department_ids, redis)

    async def _get_documents() -> list:
        if not all_document_ids:
            return []
        async with pool.acquire() as conn:
            return await get_documents(conn, all_document_ids, redis)

    async def _get_images() -> list:
        if not all_image_ids:
            return []
        async with pool.acquire() as conn:
            return await get_images(conn, all_image_ids, redis)

    async def _get_objectives() -> list:
        if not all_objective_ids:
            return []
        async with pool.acquire() as conn:
            return await get_objectives(conn, all_objective_ids, redis)

    async def _get_options() -> list:
        if not all_option_ids:
            return []
        async with pool.acquire() as conn:
            return await get_options(conn, all_option_ids, redis)

    async def _get_parameter_fields() -> list:
        if not all_parameter_field_ids:
            return []
        async with pool.acquire() as conn:
            return await get_parameter_fields(conn, all_parameter_field_ids, redis)

    async def _get_personas() -> list:
        if not all_persona_ids:
            return []
        async with pool.acquire() as conn:
            return await get_personas(conn, all_persona_ids, redis)

    async def _get_problem_statements() -> list:
        if not all_problem_statement_ids:
            return []
        async with pool.acquire() as conn:
            return await get_problem_statements(conn, all_problem_statement_ids, redis)

    async def _get_questions() -> list:
        if not all_question_ids:
            return []
        async with pool.acquire() as conn:
            return await get_questions(conn, all_question_ids, redis)

    async def _get_videos() -> list:
        if not all_video_ids:
            return []
        async with pool.acquire() as conn:
            return await get_videos(conn, all_video_ids, redis)

    (
        names_data,
        descriptions_data,
        departments_data,
        documents_data,
        images_data,
        objectives_data,
        options_data,
        parameter_fields_data,
        personas_data,
        problem_statements_data,
        questions_data,
        videos_data,
    ) = await asyncio.gather(
        _get_names(),
        _get_descriptions(),
        _get_departments(),
        _get_documents(),
        _get_images(),
        _get_objectives(),
        _get_options(),
        _get_parameter_fields(),
        _get_personas(),
        _get_problem_statements(),
        _get_questions(),
        _get_videos(),
    )

    # Build lookup maps
    name_map = {n.id: n.name for n in names_data}
    description_map = {d.id: d.description for d in descriptions_data}
    department_map = {d.id: d.name for d in departments_data}
    document_map = {d.id: d.name for d in documents_data}
    image_map = {i.id: i.name for i in images_data}
    objective_map = {o.id: o.objective for o in objectives_data}
    option_map = {o.id: o.option_text for o in options_data}
    persona_map = {p.id: p.name for p in personas_data}
    problem_statement_map = {
        ps.id: ps.problem_statement for ps in problem_statements_data
    }
    question_map = {q.id: q.question_text for q in questions_data}
    video_map = {v.id: v.name for v in videos_data}

    # Parameter fields: two-hop (parameter_field -> field -> name)
    pf_field_id_map = {pf.id: pf.field_id for pf in parameter_fields_data}
    all_field_ids = list({fid for fid in pf_field_id_map.values() if fid})
    if all_field_ids:
        async with pool.acquire() as conn:
            fields_data = await get_fields(conn, all_field_ids, redis)
    else:
        fields_data = []
    field_name_map = {f.id: f.name for f in fields_data}
    pf_name_map = {
        pf_id: field_name_map.get(field_id, "")
        for pf_id, field_id in pf_field_id_map.items()
        if field_id
    }

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
        problem_statement = (
            problem_statement_map.get(a.problem_statement_ids[0], "")
            if a.problem_statement_ids
            else ""
        )

        # Active flag
        active = "Yes" if a.active else "No"

        # Multi-select: pipe-delimited values
        departments_str = PIPE.join(
            department_map.get(did, "") for did in (a.department_ids or [])
        )
        personas_str = PIPE.join(
            persona_map.get(pid, "") for pid in (a.persona_ids or [])
        )
        documents_str = PIPE.join(
            document_map.get(did, "") for did in (a.document_ids or [])
        )
        pf_str = PIPE.join(
            pf_name_map.get(pfid, "") for pfid in (a.parameter_field_ids or [])
        )
        objectives_str = PIPE.join(
            objective_map.get(oid, "") for oid in (a.objective_ids or [])
        )
        images_str = PIPE.join(image_map.get(iid, "") for iid in (a.image_ids or []))
        videos_str = PIPE.join(video_map.get(vid, "") for vid in (a.video_ids or []))
        questions_str = PIPE.join(
            question_map.get(qid, "") for qid in (a.question_ids or [])
        )
        options_str = PIPE.join(option_map.get(oid, "") for oid in (a.option_ids or []))

        writer.writerow(
            [
                str(a.id),
                name,
                description,
                problem_statement,
                active,
                departments_str,
                personas_str,
                documents_str,
                pf_str,
                objectives_str,
                images_str,
                videos_str,
                questions_str,
                options_str,
            ]
        )

    csv_content = output.getvalue()
    row_count = len(artifacts)

    content = base64.b64encode(csv_content.encode("utf-8")).decode("ascii")
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    file_name = f"scenarios_export_{timestamp}.csv"

    return ExportScenarioApiResponse(
        content=content,
        file_name=file_name,
        mime_type="text/csv",
        row_count=row_count,
    )
