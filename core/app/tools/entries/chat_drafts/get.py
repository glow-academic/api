"""Chat drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import get_redis_client
from app.tools.entries.chat_drafts.types import GetChatDraftResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_chat_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetChatDraftResponse]:
    """Get chat_drafts entries by IDs with connection data."""
    if not ids:
        return []

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
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetChatDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            department_ids=r["department_ids"],
            pending_department_ids=r["pending_department_ids"],
            description_ids=r["description_ids"],
            pending_description_ids=r["pending_description_ids"],
            document_ids=r["document_ids"],
            pending_document_ids=r["pending_document_ids"],
            field_ids=r["field_ids"],
            pending_field_ids=r["pending_field_ids"],
            flag_ids=r["flag_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            image_ids=r["image_ids"],
            pending_image_ids=r["pending_image_ids"],
            name_ids=r["name_ids"],
            pending_name_ids=r["pending_name_ids"],
            objective_ids=r["objective_ids"],
            pending_objective_ids=r["pending_objective_ids"],
            option_ids=r["option_ids"],
            pending_option_ids=r["pending_option_ids"],
            parameter_field_ids=r["parameter_field_ids"],
            pending_parameter_field_ids=r["pending_parameter_field_ids"],
            parameter_ids=r["parameter_ids"],
            pending_parameter_ids=r["pending_parameter_ids"],
            persona_ids=r["persona_ids"],
            pending_persona_ids=r["pending_persona_ids"],
            problem_statement_ids=r["problem_statement_ids"],
            pending_problem_statement_ids=r["pending_problem_statement_ids"],
            profile_ids=r["profile_ids"],
            question_ids=r["question_ids"],
            pending_question_ids=r["pending_question_ids"],
            scenario_ids=r["scenario_ids"],
            pending_scenario_ids=r["pending_scenario_ids"],
            video_ids=r["video_ids"],
            pending_video_ids=r["pending_video_ids"],
        )
        for r in rows
    ]


async def get_chat_drafts_entries_internal(
    pool_or_conn: asyncpg.Pool | asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[GetChatDraftResponse]:
    """Cached wrapper for get_chat_drafts.

    Accepts either a Pool or a Connection — see get_names for rationale.
    """
    if not ids:
        return []

    tags = ["entries", "chat_drafts"]
    cache_key_val = cache_key(
        "/entries/chat_drafts/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return [
                GetChatDraftResponse.model_validate(i) for i in cached.get("items", [])
            ]

    if isinstance(pool_or_conn, asyncpg.Pool):
        async with pool_or_conn.acquire() as conn:
            items = await get_chat_drafts(conn, ids)
    else:
        items = await get_chat_drafts(pool_or_conn, ids)

    await set_cached(
        cache_key_val,
        {"items": [i.model_dump(mode="json") for i in items]},
        ttl=60,
        tags=tags,
        redis=get_redis_client(),
    )

    return items
