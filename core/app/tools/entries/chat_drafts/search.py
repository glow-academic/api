"""Chat drafts SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.chat_drafts.types import GetChatDraftResponse
from app.utils.cache.hedged_row import hedged_search


async def search_chat_drafts(
    conn: asyncpg.Connection,
    redis: Redis,
    session_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    name: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    mcp: bool | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
) -> list[GetChatDraftResponse]:
    """Search chat_drafts with declarative filters and connection data."""
    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT doc.documents_id) FILTER (WHERE doc.documents_id IS NOT NULL), '{}') AS document_ids,
            COALESCE(ARRAY_AGG(DISTINCT doc.documents_id) FILTER (WHERE doc.documents_id IS NOT NULL AND doc.active = false), '{}') AS pending_document_ids,
            COALESCE(ARRAY_AGG(DISTINCT fld.fields_id) FILTER (WHERE fld.fields_id IS NOT NULL), '{}') AS field_ids,
            COALESCE(ARRAY_AGG(DISTINCT fld.fields_id) FILTER (WHERE fld.fields_id IS NOT NULL AND fld.active = false), '{}') AS pending_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL), '{}') AS image_ids,
            COALESCE(ARRAY_AGG(DISTINCT img.images_id) FILTER (WHERE img.images_id IS NOT NULL AND img.active = false), '{}') AS pending_image_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT obj.objectives_id) FILTER (WHERE obj.objectives_id IS NOT NULL), '{}') AS objective_ids,
            COALESCE(ARRAY_AGG(DISTINCT obj.objectives_id) FILTER (WHERE obj.objectives_id IS NOT NULL AND obj.active = false), '{}') AS pending_objective_ids,
            COALESCE(ARRAY_AGG(DISTINCT opt.options_id) FILTER (WHERE opt.options_id IS NOT NULL), '{}') AS option_ids,
            COALESCE(ARRAY_AGG(DISTINCT opt.options_id) FILTER (WHERE opt.options_id IS NOT NULL AND opt.active = false), '{}') AS pending_option_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL), '{}') AS parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL AND pf.active = false), '{}') AS pending_parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT par.parameters_id) FILTER (WHERE par.parameters_id IS NOT NULL), '{}') AS parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT par.parameters_id) FILTER (WHERE par.parameters_id IS NOT NULL AND par.active = false), '{}') AS pending_parameter_ids,
            COALESCE(ARRAY_AGG(DISTINCT per.personas_id) FILTER (WHERE per.personas_id IS NOT NULL), '{}') AS persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT per.personas_id) FILTER (WHERE per.personas_id IS NOT NULL AND per.active = false), '{}') AS pending_persona_ids,
            COALESCE(ARRAY_AGG(DISTINCT ps.problem_statements_id) FILTER (WHERE ps.problem_statements_id IS NOT NULL), '{}') AS problem_statement_ids,
            COALESCE(ARRAY_AGG(DISTINCT ps.problem_statements_id) FILTER (WHERE ps.problem_statements_id IS NOT NULL AND ps.active = false), '{}') AS pending_problem_statement_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.questions_id) FILTER (WHERE q.questions_id IS NOT NULL), '{}') AS question_ids,
            COALESCE(ARRAY_AGG(DISTINCT q.questions_id) FILTER (WHERE q.questions_id IS NOT NULL AND q.active = false), '{}') AS pending_question_ids,
            COALESCE(ARRAY_AGG(DISTINCT sc.scenarios_id) FILTER (WHERE sc.scenarios_id IS NOT NULL), '{}') AS scenario_ids,
            COALESCE(ARRAY_AGG(DISTINCT sc.scenarios_id) FILTER (WHERE sc.scenarios_id IS NOT NULL AND sc.active = false), '{}') AS pending_scenario_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.videos_id) FILTER (WHERE v.videos_id IS NOT NULL), '{}') AS video_ids
            ,
            COALESCE(ARRAY_AGG(DISTINCT v.videos_id) FILTER (WHERE v.videos_id IS NOT NULL AND v.active = false), '{}') AS pending_video_ids
        FROM chat_drafts_entry d
        LEFT JOIN chat_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN chat_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN chat_drafts_documents_connection doc ON doc.draft_id = d.id
        LEFT JOIN chat_drafts_fields_connection fld ON fld.draft_id = d.id
        LEFT JOIN chat_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN chat_drafts_images_connection img ON img.draft_id = d.id
        LEFT JOIN chat_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN chat_drafts_objectives_connection obj ON obj.draft_id = d.id
        LEFT JOIN chat_drafts_options_connection opt ON opt.draft_id = d.id
        LEFT JOIN chat_drafts_parameter_fields_connection pf ON pf.draft_id = d.id
        LEFT JOIN chat_drafts_parameters_connection par ON par.draft_id = d.id
        LEFT JOIN chat_drafts_personas_connection per ON per.draft_id = d.id
        LEFT JOIN chat_drafts_problem_statements_connection ps ON ps.draft_id = d.id
        LEFT JOIN chat_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN chat_drafts_questions_connection q ON q.draft_id = d.id
        LEFT JOIN chat_drafts_scenarios_connection sc ON sc.draft_id = d.id
        LEFT JOIN chat_drafts_videos_connection v ON v.draft_id = d.id
        WHERE d.active = true
          AND ($1::uuid[] IS NULL OR d.session_id = ANY($1))
          AND ($2::uuid[] IS NULL OR p.profiles_id = ANY($2))
          AND ($3::timestamptz IS NULL OR d.created_at >= $3)
          AND ($4::timestamptz IS NULL OR d.created_at <= $4)
          AND ($5::boolean IS NULL OR d.mcp = $5)
          AND ($6::text IS NULL OR d.name ILIKE '%' || $6 || '%')
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        LIMIT $7 OFFSET $8
        """,
        session_ids,
        profile_ids,
        date_from,
        date_to,
        mcp,
        name,
        limit + offset + 1000,
        0,
    )

    def _strs(v):
        return [str(x) for x in (v or [])]

    mv_dicts: list[dict] = [
        {
            "id": str(r["id"]),
            "created_at": r["created_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "name": r["name"],
            "department_ids": _strs(r["department_ids"]),
            "pending_department_ids": _strs(r["pending_department_ids"]),
            "description_ids": _strs(r["description_ids"]),
            "pending_description_ids": _strs(r["pending_description_ids"]),
            "document_ids": _strs(r["document_ids"]),
            "pending_document_ids": _strs(r["pending_document_ids"]),
            "field_ids": _strs(r["field_ids"]),
            "pending_field_ids": _strs(r["pending_field_ids"]),
            "flag_ids": _strs(r["flag_ids"]),
            "pending_flag_ids": _strs(r["pending_flag_ids"]),
            "image_ids": _strs(r["image_ids"]),
            "pending_image_ids": _strs(r["pending_image_ids"]),
            "name_ids": _strs(r["name_ids"]),
            "pending_name_ids": _strs(r["pending_name_ids"]),
            "objective_ids": _strs(r["objective_ids"]),
            "pending_objective_ids": _strs(r["pending_objective_ids"]),
            "option_ids": _strs(r["option_ids"]),
            "pending_option_ids": _strs(r["pending_option_ids"]),
            "parameter_field_ids": _strs(r["parameter_field_ids"]),
            "pending_parameter_field_ids": _strs(r["pending_parameter_field_ids"]),
            "parameter_ids": _strs(r["parameter_ids"]),
            "pending_parameter_ids": _strs(r["pending_parameter_ids"]),
            "persona_ids": _strs(r["persona_ids"]),
            "pending_persona_ids": _strs(r["pending_persona_ids"]),
            "problem_statement_ids": _strs(r["problem_statement_ids"]),
            "pending_problem_statement_ids": _strs(r["pending_problem_statement_ids"]),
            "profile_ids": _strs(r["profile_ids"]),
            "question_ids": _strs(r["question_ids"]),
            "pending_question_ids": _strs(r["pending_question_ids"]),
            "scenario_ids": _strs(r["scenario_ids"]),
            "pending_scenario_ids": _strs(r["pending_scenario_ids"]),
            "video_ids": _strs(r["video_ids"]),
            "pending_video_ids": _strs(r["pending_video_ids"]),
        }
        for r in rows
    ]

    session_ids_str = {str(x) for x in session_ids} if session_ids else None
    profile_ids_str = {str(x) for x in profile_ids} if profile_ids else None

    def _parse_ts(ts):
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        return ts

    name_lc = name.lower() if name else None

    def matches(row: dict) -> bool:
        if not row.get("active"):
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        if profile_ids_str is not None:
            row_profiles = {str(x) for x in (row.get("profile_ids") or [])}
            if not (row_profiles & profile_ids_str):
                return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        if mcp is not None and row.get("mcp") != mcp:
            return False
        if name_lc is not None:
            row_name = (row.get("name") or "").lower()
            if name_lc not in row_name:
                return False
        return True

    merged = await hedged_search(
        redis,
        "chat_drafts",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetChatDraftResponse.model_validate(r) for r in merged]
