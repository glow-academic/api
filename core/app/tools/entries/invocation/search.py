"""Invocation SEARCH — declarative filters on base table + connections."""

from datetime import datetime
from datetime import datetime as _dt
from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.invocation.types import GetInvocationResponse
from app.utils.cache.hedged_row import hedged_search


async def search_invocations(
    conn: asyncpg.Connection,
    redis: Redis,
    benchmark_ids: list[UUID] | None = None,
    session_ids: list[UUID] | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 20,
    offset: int = 0,
    bypass_cache: bool = False,
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
        limit + offset + 1000,
        0,
    )

    mv_dicts = [
        {
            "id": str(r["id"]),
            "benchmark_id": str(r["benchmark_id"]) if r["benchmark_id"] else None,
            "session_id": str(r["session_id"]) if r["session_id"] else None,
            "use_custom": r["use_custom"],
            "position": r["position"],
            "created_at": r["created_at"],
            "active": r["active"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "department_ids": [str(x) for x in (r["department_ids"] or [])],
            "description_ids": [str(x) for x in (r["description_ids"] or [])],
            "flag_ids": [str(x) for x in (r["flag_ids"] or [])],
            "key_ids": [str(x) for x in (r["key_ids"] or [])],
            "modality_ids": [str(x) for x in (r["modality_ids"] or [])],
            "model_flag_ids": [str(x) for x in (r["model_flag_ids"] or [])],
            "model_position_ids": [str(x) for x in (r["model_position_ids"] or [])],
            "model_rubric_ids": [str(x) for x in (r["model_rubric_ids"] or [])],
            "model_ids": [str(x) for x in (r["model_ids"] or [])],
            "name_ids": [str(x) for x in (r["name_ids"] or [])],
            "quality_ids": [str(x) for x in (r["quality_ids"] or [])],
            "reasoning_level_ids": [str(x) for x in (r["reasoning_level_ids"] or [])],
            "temperature_level_ids": [str(x) for x in (r["temperature_level_ids"] or [])],
            "voice_ids": [str(x) for x in (r["voice_ids"] or [])],
        }
        for r in rows
    ]

    benchmark_ids_str = {str(b) for b in benchmark_ids} if benchmark_ids else None
    session_ids_str = {str(s) for s in session_ids} if session_ids else None

    def _parse_ts(ts: object) -> datetime | None:
        if isinstance(ts, str):
            return _dt.fromisoformat(ts)
        if isinstance(ts, datetime):
            return ts
        return None

    def matches(row: dict) -> bool:
        if not row.get("active", True):
            return False
        if benchmark_ids_str is not None and str(row.get("benchmark_id")) not in benchmark_ids_str:
            return False
        if session_ids_str is not None and str(row.get("session_id")) not in session_ids_str:
            return False
        ts = _parse_ts(row.get("created_at"))
        if date_from is not None and (ts is None or ts < date_from):
            return False
        if date_to is not None and (ts is None or ts > date_to):
            return False
        return True

    merged = await hedged_search(
        redis,
        "invocation",
        mv_rows=mv_dicts,
        matches_filter=matches,
        limit=limit,
        offset=offset,
        bypass_cache=bypass_cache,
    )
    return [GetInvocationResponse.model_validate(r) for r in merged]
