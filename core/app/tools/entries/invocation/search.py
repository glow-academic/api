"""Invocation SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.invocation.types import GetInvocationResponse


async def search_invocations(
    conn: asyncpg.Connection,
    benchmark_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[GetInvocationResponse]:
    """Search invocations with declarative filters and connection data."""
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
        WHERE e.active = true
          AND ($1::uuid[] IS NULL OR e.benchmark_id = ANY($1))
          AND ($2::uuid[] IS NULL OR e.session_id = ANY($2))
          AND ($3::timestamptz IS NULL OR e.created_at >= $3)
          AND ($4::timestamptz IS NULL OR e.created_at <= $4)
        GROUP BY e.id, e.benchmark_id, e.session_id, e.use_custom, e."position",
                 e.created_at, e.active, e.generated, e.mcp
        ORDER BY e.created_at DESC
        LIMIT $5 OFFSET $6
        """,
        benchmark_ids,
        session_ids,
        date_from,
        date_to,
        limit,
        offset,
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
