"""Invocation GET — read from base table + connection tables."""

from dataclasses import dataclass, field
from uuid import UUID

import asyncpg  # type: ignore

from app.infra.globals import get_redis_client
from app.tools.entries.invocation.types import GetInvocationResponse
from app.utils.cache.cache_key import cache_key
from app.utils.cache.get_cached import get_cached
from app.utils.cache.set_cached import set_cached


async def get_invocations(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetInvocationResponse]:
    """Get invocation entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            e.id, e.benchmark_id, e.session_id, e.use_custom, e."position",
            e.created_at, e.active, e.generated, e.mcp,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dsc.descriptions_id) FILTER (WHERE dsc.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT flg.flags_id) FILTER (WHERE flg.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT ky.keys_id) FILTER (WHERE ky.keys_id IS NOT NULL), '{}') AS key_ids,
            COALESCE(ARRAY_AGG(DISTINCT mod_c.modalities_id) FILTER (WHERE mod_c.modalities_id IS NOT NULL), '{}') AS modality_ids,
            COALESCE(ARRAY_AGG(DISTINCT mf.model_flags_id) FILTER (WHERE mf.model_flags_id IS NOT NULL), '{}') AS model_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT mp.model_positions_id) FILTER (WHERE mp.model_positions_id IS NOT NULL), '{}') AS model_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT mr.model_rubrics_id) FILTER (WHERE mr.model_rubrics_id IS NOT NULL), '{}') AS model_rubric_ids,
            COALESCE(ARRAY_AGG(DISTINCT mdl.models_id) FILTER (WHERE mdl.models_id IS NOT NULL), '{}') AS model_ids,
            COALESCE(ARRAY_AGG(DISTINCT nm.names_id) FILTER (WHERE nm.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT ql.qualities_id) FILTER (WHERE ql.qualities_id IS NOT NULL), '{}') AS quality_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.reasoning_levels_id) FILTER (WHERE rl.reasoning_levels_id IS NOT NULL), '{}') AS reasoning_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT tl.temperature_levels_id) FILTER (WHERE tl.temperature_levels_id IS NOT NULL), '{}') AS temperature_level_ids,
            COALESCE(ARRAY_AGG(DISTINCT vc.voices_id) FILTER (WHERE vc.voices_id IS NOT NULL), '{}') AS voice_ids
        FROM invocation_entry e
        LEFT JOIN invocation_departments_connection dep ON dep.invocation_id = e.id
        LEFT JOIN invocation_descriptions_connection dsc ON dsc.invocation_id = e.id
        LEFT JOIN invocation_flags_connection flg ON flg.invocation_id = e.id
        LEFT JOIN invocation_keys_connection ky ON ky.invocation_id = e.id
        LEFT JOIN invocation_modalities_connection mod_c ON mod_c.invocation_id = e.id
        LEFT JOIN invocation_model_flags_connection mf ON mf.invocation_id = e.id
        LEFT JOIN invocation_model_positions_connection mp ON mp.invocation_id = e.id
        LEFT JOIN invocation_model_rubrics_connection mr ON mr.invocation_id = e.id
        LEFT JOIN invocation_models_connection mdl ON mdl.invocation_id = e.id
        LEFT JOIN invocation_names_connection nm ON nm.invocation_id = e.id
        LEFT JOIN invocation_qualities_connection ql ON ql.invocation_id = e.id
        LEFT JOIN invocation_reasoning_levels_connection rl ON rl.invocation_id = e.id
        LEFT JOIN invocation_temperature_levels_connection tl ON tl.invocation_id = e.id
        LEFT JOIN invocation_voices_connection vc ON vc.invocation_id = e.id
        WHERE e.id = ANY($1) AND e.active = true
        GROUP BY e.id, e.benchmark_id, e.session_id, e.use_custom, e."position",
                 e.created_at, e.active, e.generated, e.mcp
        ORDER BY e.created_at DESC
        """,
        ids,
    )

    return [
        GetInvocationResponse(
            id=r["id"],
            benchmark_id=r["benchmark_id"],
            session_id=r["session_id"],
            use_custom=r["use_custom"],
            position=r["position"],
            created_at=r["created_at"],
            active=r["active"],
            generated=r["generated"],
            mcp=r["mcp"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            key_ids=r["key_ids"],
            modality_ids=r["modality_ids"],
            model_flag_ids=r["model_flag_ids"],
            model_position_ids=r["model_position_ids"],
            model_rubric_ids=r["model_rubric_ids"],
            model_ids=r["model_ids"],
            name_ids=r["name_ids"],
            quality_ids=r["quality_ids"],
            reasoning_level_ids=r["reasoning_level_ids"],
            temperature_level_ids=r["temperature_level_ids"],
            voice_ids=r["voice_ids"],
        )
        for r in rows
    ]


async def get_invocation_entries_internal(
    conn: asyncpg.Connection,
    ids: list[UUID],
    bypass_cache: bool = False,
) -> list[GetInvocationResponse]:
    """Cached wrapper for get_invocations."""
    if not ids:
        return []

    tags = ["entries", "invocation"]
    cache_key_val = cache_key(
        "/v5/entries/invocation/get",
        {"ids": [str(id) for id in ids]},
    )

    if not bypass_cache:
        cached = await get_cached(cache_key_val, redis=get_redis_client())
        if cached:
            return [
                GetInvocationResponse.model_validate(i) for i in cached.get("items", [])
            ]

    items = await get_invocations(conn, ids)

    await set_cached(
        cache_key_val,
        {"items": [i.model_dump(mode="json") for i in items]},
        ttl=60,
        tags=tags,
        redis=get_redis_client(),
    )

    return items


# =============================================================================
# Invocation View (for artifact bundle endpoint)
# =============================================================================


@dataclass
class InvocationViewData:
    """Thin view data returned by get_invocation_view_internal."""

    profile_has_access: bool = False
    suite_entry_id: UUID | None = None
    benchmark_id: UUID | None = None
    department_ids: list[UUID] = field(default_factory=list)
    model_ids: list[UUID] = field(default_factory=list)
    prompt_ids: list[UUID] = field(default_factory=list)
    instruction_ids: list[UUID] = field(default_factory=list)
    voice_ids: list[UUID] = field(default_factory=list)
    temperature_level_ids: list[UUID] = field(default_factory=list)
    reasoning_level_ids: list[UUID] = field(default_factory=list)
    tool_ids: list[UUID] = field(default_factory=list)
    key_ids: list[UUID] = field(default_factory=list)


async def get_invocation_view_internal(
    conn: asyncpg.Connection,
    profile_id: UUID,
    suite_entry_id: UUID,
) -> InvocationViewData:
    """Query invocation_mv with profile access check for bundle artifact endpoint."""
    row = await conn.fetchrow(
        """
        WITH bundle AS (
            SELECT im.*
            FROM invocation_mv im
            WHERE im.invocation_entry_id = $2
            LIMIT 1
        ),
        benchmark_cohorts AS (
            SELECT COALESCE(bm.cohort_ids, ARRAY[]::uuid[]) AS cohort_ids
            FROM bundle b
            LEFT JOIN benchmark_mv bm ON bm.benchmark_id = b.benchmark_id
            LIMIT 1
        ),
        access_check AS (
            SELECT EXISTS (
                SELECT 1
                FROM benchmark_cohorts bc
                JOIN profile_profiles_junction ppj
                  ON ppj.profile_id = $1 AND ppj.active = true
                JOIN cohort_profiles_junction cpj
                  ON cpj.profiles_id = ppj.profiles_id AND cpj.active = true
                JOIN cohort_cohorts_junction ccj
                  ON ccj.cohort_id = cpj.cohort_id AND ccj.active = true
                JOIN cohorts_resource cr
                  ON cr.id = ccj.cohorts_id AND cr.active = true
                WHERE ccj.cohorts_id = ANY(bc.cohort_ids)
            ) AS profile_has_access
        )
        SELECT
            COALESCE(ac.profile_has_access, false) AS profile_has_access,
            b.invocation_entry_id,
            b.benchmark_id,
            b.department_ids,
            b.model_ids,
            b.voice_ids,
            b.temperature_level_ids,
            b.reasoning_level_ids,
            b.key_ids
        FROM bundle b
        LEFT JOIN access_check ac ON TRUE
        """,
        profile_id,
        suite_entry_id,
    )

    if not row:
        return InvocationViewData()

    return InvocationViewData(
        profile_has_access=row["profile_has_access"] or False,
        suite_entry_id=row["invocation_entry_id"],
        benchmark_id=row["benchmark_id"],
        department_ids=list(row["department_ids"] or []),
        model_ids=list(row["model_ids"] or []),
        voice_ids=list(row["voice_ids"] or []),
        temperature_level_ids=list(row["temperature_level_ids"] or []),
        reasoning_level_ids=list(row["reasoning_level_ids"] or []),
        key_ids=list(row["key_ids"] or []),
    )
