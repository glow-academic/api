"""Scenario drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.scenario_drafts.types import GetScenarioDraftResponse


async def search_scenario_drafts(
    conn: asyncpg.Connection,
    group_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetScenarioDraftResponse]:
    """Search scenario_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT doc.documents_id) FILTER (WHERE doc.documents_id IS NOT NULL), '{}') AS document_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL), '{}') AS image_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT obj.objectives_id) FILTER (WHERE obj.objectives_id IS NOT NULL), '{}') AS objective_ids,
            COALESCE(ARRAY_AGG(DISTINCT opt.options_id) FILTER (WHERE opt.options_id IS NOT NULL), '{}') AS option_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL), '{}') AS parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT per.personas_id) FILTER (WHERE per.personas_id IS NOT NULL), '{}') AS persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT ps.problem_statements_id) FILTER (WHERE ps.problem_statements_id IS NOT NULL), '{}') AS problem_statement_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.questions_id) FILTER (WHERE q.questions_id IS NOT NULL), '{}') AS question_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.videos_id) FILTER (WHERE v.videos_id IS NOT NULL), '{}') AS video_ids
        FROM scenario_drafts_entry d
        LEFT JOIN scenario_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN scenario_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN scenario_drafts_documents_connection doc ON doc.draft_id = d.id
        LEFT JOIN scenario_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN scenario_drafts_images_connection img ON img.draft_id = d.id
        LEFT JOIN scenario_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN scenario_drafts_objectives_connection obj ON obj.draft_id = d.id
        LEFT JOIN scenario_drafts_options_connection opt ON opt.draft_id = d.id
        LEFT JOIN scenario_drafts_parameter_fields_connection pf ON pf.draft_id = d.id
        LEFT JOIN scenario_drafts_personas_connection per ON per.draft_id = d.id
        LEFT JOIN scenario_drafts_problem_statements_connection ps ON ps.draft_id = d.id
        LEFT JOIN scenario_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN scenario_drafts_questions_connection q ON q.draft_id = d.id
        LEFT JOIN scenario_drafts_videos_connection v ON v.draft_id = d.id
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.group_id = ANY($1))
          AND ($2::uuid[] IS NULL OR d.session_id = ANY($2))
          AND ($3::uuid[] IS NULL OR p.profiles_id = ANY($3))
          AND ($4::timestamptz IS NULL OR d.created_at >= $4)
          AND ($5::timestamptz IS NULL OR d.created_at <= $5)
          AND ($6::boolean IS NULL OR d.mcp = $6)
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        LIMIT $7 OFFSET $8
        """,
        group_ids,
        session_ids,
        profile_ids,
        date_from,
        date_to,
        mcp,
        limit,
        offset,
    )

    return [
        GetScenarioDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            document_ids=r["document_ids"],
            flag_ids=r["flag_ids"],
            image_ids=r["image_ids"],
            name_ids=r["name_ids"],
            objective_ids=r["objective_ids"],
            option_ids=r["option_ids"],
            parameter_field_ids=r["parameter_field_ids"],
            persona_ids=r["persona_ids"],
            problem_statement_ids=r["problem_statement_ids"],
            profile_ids=r["profile_ids"],
            question_ids=r["question_ids"],
            video_ids=r["video_ids"],
        )
        for r in rows
    ]
