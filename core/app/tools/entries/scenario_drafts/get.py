"""Scenario drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.scenario_drafts.types import GetScenarioDraftResponse


async def get_scenario_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
) -> list[GetScenarioDraftResponse]:
    """Get scenario_drafts entries by IDs with connection data.

    ``active=True`` (default) — only committed drafts.
    ``active=None`` — both committed and dormant pending. Use for
    ack short-circuit / auto-accept lookups.
    """
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
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
            COALESCE(ARRAY_AGG(DISTINCT v.videos_id) FILTER (WHERE v.videos_id IS NOT NULL), '{}') AS video_ids,
            -- Pending IDs (connections with active=false)
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT ps.problem_statements_id) FILTER (WHERE ps.problem_statements_id IS NOT NULL AND ps.active = false), '{}') AS pending_problem_statement_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT per.personas_id) FILTER (WHERE per.personas_id IS NOT NULL AND per.active = false), '{}') AS pending_persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT doc.documents_id) FILTER (WHERE doc.documents_id IS NOT NULL AND doc.active = false), '{}') AS pending_document_ids,
            COALESCE(ARRAY_AGG(DISTINCT obj.objectives_id) FILTER (WHERE obj.objectives_id IS NOT NULL AND obj.active = false), '{}') AS pending_objective_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL AND img.active = false), '{}') AS pending_image_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.videos_id) FILTER (WHERE v.videos_id IS NOT NULL AND v.active = false), '{}') AS pending_video_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.questions_id) FILTER (WHERE q.questions_id IS NOT NULL AND q.active = false), '{}') AS pending_question_ids,
            COALESCE(ARRAY_AGG(DISTINCT opt.options_id) FILTER (WHERE opt.options_id IS NOT NULL AND opt.active = false), '{}') AS pending_option_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL AND pf.active = false), '{}') AS pending_parameter_field_ids
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
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
        active,
    )

    return [
        GetScenarioDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
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
            pending_name_ids=r["pending_name_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_problem_statement_ids=r["pending_problem_statement_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_persona_ids=r["pending_persona_ids"],
            pending_document_ids=r["pending_document_ids"],
            pending_objective_ids=r["pending_objective_ids"],
            pending_image_ids=r["pending_image_ids"],
            pending_video_ids=r["pending_video_ids"],
            pending_question_ids=r["pending_question_ids"],
            pending_option_ids=r["pending_option_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_parameter_field_ids=r["pending_parameter_field_ids"],
        )
        for r in rows
    ]
