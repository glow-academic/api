"""chat/get — reusable data-access layer."""

import json
from dataclasses import dataclass, field
from uuid import UUID

import asyncpg

from app.infra.globals import get_redis_client
from app.tools.entries.chat.types import GetChatResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached

MV_NAME = "chat_mv"


async def get_chats(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetChatResponse]:
    """Get chat entries by IDs from chat_mv."""
    if not ids:
        return []

    rows = await conn.fetch(
        f"""
        SELECT chat_entry_id, parent_id, scenario_id,
               department_ids, document_ids, parameter_field_ids,
               question_ids, option_ids, video_ids, image_ids,
               problem_statement_ids, objective_ids, flag_ids,
               name_ids, description_ids, persona_ids,
               rubric_ids, standard_ids, standard_group_ids,
               video_enabled, problem_statement_enabled,
               objectives_enabled, images_enabled, questions_enabled,
               position, time_limit, negative_time
        FROM {MV_NAME}
        WHERE chat_entry_id = ANY($1)
        """,
        ids,
    )

    return [
        GetChatResponse(
            id=r["chat_entry_id"],
            parent_id=r["parent_id"],
            scenario_id=r["scenario_id"],
            department_ids=r["department_ids"] or [],
            document_ids=r["document_ids"] or [],
            parameter_field_ids=r["parameter_field_ids"] or [],
            question_ids=r["question_ids"] or [],
            option_ids=r["option_ids"] or [],
            video_ids=r["video_ids"] or [],
            image_ids=r["image_ids"] or [],
            problem_statement_ids=r["problem_statement_ids"] or [],
            objective_ids=r["objective_ids"] or [],
            flag_ids=r["flag_ids"] or [],
            name_ids=r["name_ids"] or [],
            description_ids=r["description_ids"] or [],
            persona_ids=r["persona_ids"] or [],
            rubric_ids=r["rubric_ids"] or [],
            standard_ids=r["standard_ids"] or [],
            standard_group_ids=r["standard_group_ids"] or [],
            video_enabled=r["video_enabled"],
            problem_statement_enabled=r["problem_statement_enabled"],
            objectives_enabled=r["objectives_enabled"],
            images_enabled=r["images_enabled"],
            questions_enabled=r["questions_enabled"],
            position=r["position"],
            time_limit=r["time_limit"],
            negative_time=r["negative_time"],
        )
        for r in rows
    ]


async def get_chat_entries_internal(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[dict]:
    """Internal function to fetch chat entries by IDs from chat_mv."""
    if not ids:
        return []

    tags = ["entries", "chat"]
    cache_key_val = cache_key(
        "/v5/entries/chat/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return list(cached.get("items", []))

    result = await conn.fetchval(
        """
        SELECT COALESCE(jsonb_agg(to_jsonb(m)), '[]'::jsonb)
        FROM (
            SELECT
                m.chat_entry_id,
                m.parent_id,
                m.scenario_id,
                m.department_ids,
                m.persona_ids,
                m.document_ids,
                m.parameter_field_ids,
                m.question_ids,
                m.option_ids,
                m.video_ids,
                m.image_ids,
                m.problem_statement_ids,
                m.objective_ids,
                m.flag_ids,
                m.name_ids,
                m.description_ids,
                m.rubric_ids,
                m.standard_ids,
                m.standard_group_ids,
                m.video_enabled,
                m.problem_statement_enabled,
                m.objectives_enabled,
                m.images_enabled,
                m.questions_enabled,
                m."position",
                m.time_limit,
                m.negative_time,
                m.name,
                m.description,
                m.use_custom,
                m.use_previous,
                m.audio_enabled,
                m.text_enabled,
                m.hints_enabled,
                m.copy_paste_allowed,
                m.show_images,
                m.show_objectives,
                m.show_problem_statement,
                m.analyses_enabled,
                m.improvements_enabled,
                m.replacements_enabled,
                m.strengths_enabled,
                m.generate_problem_statements,
                m.generate_objectives,
                m.generate_videos,
                m.generate_images,
                m.generate_questions,
                m.generate_names,
                m.generate_descriptions,
                m.generate_personas,
                m.generate_documents,
                m.generate_options,
                m.generate_parameter_fields,
                m.created_at,
                m.active
            FROM chat_mv m
            WHERE m.chat_entry_id = ANY($1)
        ) m
        """,
        ids,
    )

    items: list[dict] = (
        json.loads(result) if isinstance(result, str) else (result or [])
    )

    await set_cached(
        cache_key_val,
        {"items": items if isinstance(items, list) else []},
        ttl=60,
        tags=tags,
        redis=get_redis_client(),
    )

    return items


# =============================================================================
# Chat View (for artifact bundle endpoint)
# =============================================================================


@dataclass
class ChatViewData:
    """Thin view data returned by get_chat_view_internal."""

    profile_has_access: bool = False
    chat_entry_id: UUID | None = None
    parent_id: UUID | None = None
    scenario_id: UUID | None = None
    department_ids: list[UUID] = field(default_factory=list)
    persona_ids: list[UUID] = field(default_factory=list)
    document_ids: list[UUID] = field(default_factory=list)
    parameter_field_ids: list[UUID] = field(default_factory=list)
    question_ids: list[UUID] = field(default_factory=list)
    option_ids: list[UUID] = field(default_factory=list)
    video_ids: list[UUID] = field(default_factory=list)
    image_ids: list[UUID] = field(default_factory=list)
    problem_statement_ids: list[UUID] = field(default_factory=list)
    objective_ids: list[UUID] = field(default_factory=list)
    flag_ids: list[UUID] = field(default_factory=list)
    name_ids: list[UUID] = field(default_factory=list)
    description_ids: list[UUID] = field(default_factory=list)
    video_enabled: bool = False
    problem_statement_enabled: bool = False
    objectives_enabled: bool = False
    images_enabled: bool = False
    questions_enabled: bool = False


async def get_chat_view_internal(
    conn: asyncpg.Connection,
    profile_id: UUID,
    chat_entry_id: UUID,
) -> ChatViewData:
    """Query chat_mv with profile access check for bundle artifact endpoint."""
    row = await conn.fetchrow(
        """
        WITH bundle AS (
            SELECT cm.*
            FROM chat_mv cm
            WHERE cm.chat_entry_id = $2
            LIMIT 1
        ),
        parent_cohorts AS (
            SELECT COALESCE(mh.cohort_ids, mp.cohort_ids, ARRAY[]::uuid[]) AS cohort_ids
            FROM bundle b
            LEFT JOIN home_mv mh ON mh.home_id = b.parent_id
            LEFT JOIN practice_mv mp ON mp.practice_id = b.parent_id
            LIMIT 1
        ),
        access_check AS (
            SELECT EXISTS (
                SELECT 1
                FROM parent_cohorts pc
                JOIN profile_profiles_junction ppj
                  ON ppj.profile_id = $1 AND ppj.active = true
                JOIN cohort_profiles_junction cpj
                  ON cpj.profiles_id = ppj.profiles_id AND cpj.active = true
                JOIN cohort_cohorts_junction ccj
                  ON ccj.cohort_id = cpj.cohort_id AND ccj.active = true
                JOIN cohorts_resource cr
                  ON cr.id = ccj.cohorts_id AND cr.active = true
                WHERE ccj.cohorts_id = ANY(pc.cohort_ids)
            ) AS profile_has_access
        )
        SELECT
            COALESCE(ac.profile_has_access, false) AS profile_has_access,
            b.chat_entry_id,
            b.parent_id,
            b.scenario_id,
            b.department_ids,
            b.persona_ids,
            b.document_ids,
            b.parameter_field_ids,
            b.question_ids,
            b.option_ids,
            b.video_ids,
            b.image_ids,
            b.problem_statement_ids,
            b.objective_ids,
            b.flag_ids,
            b.name_ids,
            b.description_ids,
            b.video_enabled,
            b.problem_statement_enabled,
            b.objectives_enabled,
            b.images_enabled,
            b.questions_enabled
        FROM bundle b
        LEFT JOIN access_check ac ON TRUE
        """,
        profile_id,
        chat_entry_id,
    )

    if not row:
        return ChatViewData()

    return ChatViewData(
        profile_has_access=row["profile_has_access"] or False,
        chat_entry_id=row["chat_entry_id"],
        parent_id=row["parent_id"],
        scenario_id=row["scenario_id"],
        department_ids=list(row["department_ids"] or []),
        persona_ids=list(row["persona_ids"] or []),
        document_ids=list(row["document_ids"] or []),
        parameter_field_ids=list(row["parameter_field_ids"] or []),
        question_ids=list(row["question_ids"] or []),
        option_ids=list(row["option_ids"] or []),
        video_ids=list(row["video_ids"] or []),
        image_ids=list(row["image_ids"] or []),
        problem_statement_ids=list(row["problem_statement_ids"] or []),
        objective_ids=list(row["objective_ids"] or []),
        flag_ids=list(row["flag_ids"] or []),
        name_ids=list(row["name_ids"] or []),
        description_ids=list(row["description_ids"] or []),
        video_enabled=row["video_enabled"] or False,
        problem_statement_enabled=row["problem_statement_enabled"] or False,
        objectives_enabled=row["objectives_enabled"] or False,
        images_enabled=row["images_enabled"] or False,
        questions_enabled=row["questions_enabled"] or False,
    )
