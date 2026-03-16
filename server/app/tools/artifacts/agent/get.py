"""Agent artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.agent.types import GetAgentsResponse

TABLE = "agent_artifact"
ARTIFACT_FK = "agent_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "agent_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "agent_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "agent_departments_junction", "departments_id", "department_ids"),
    ("flags", "agent_flags_junction", "flags_id", "flag_ids"),
    ("models", "agent_models_junction", "models_id", "model_ids"),
    (
        "reasoning_levels",
        "agent_reasoning_levels_junction",
        "reasoning_levels_id",
        "reasoning_level_ids",
    ),
    (
        "temperature_levels",
        "agent_temperature_levels_junction",
        "temperature_levels_id",
        "temperature_level_ids",
    ),
    ("tools", "agent_tools_junction", "tools_id", "tool_ids"),
    ("voices", "agent_voices_junction", "voices_id", "voice_ids"),
    ("qualities", "agent_qualities_junction", "qualities_id", "quality_ids"),
    ("rubrics", "agent_rubrics_junction", "rubrics_id", "rubric_ids"),
    ("agents", "agent_agents_junction", "agents_id", "agent_ids"),
]


async def get_agents(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    models: bool = False,
    reasoning_levels: bool = False,
    temperature_levels: bool = False,
    tools: bool = False,
    voices: bool = False,
    qualities: bool = False,
    rubrics: bool = False,
    agents: bool = False,
) -> list[GetAgentsResponse]:
    """Get agent artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "models": models,
        "reasoning_levels": reasoning_levels,
        "temperature_levels": temperature_levels,
        "tools": tools,
        "voices": voices,
        "qualities": qualities,
        "rubrics": rubrics,
        "agents": agents,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

    # Build dynamic query
    columns = [
        "p.id",
        "p.created_at",
        "p.updated_at",
        "p.generated",
        "p.mcp",
        "p.active",
    ]
    joins: list[str] = []

    for i, (table, col, field) in enumerate(active_junctions):
        alias = f"j{i}"
        joins.append(
            f"LEFT JOIN {table} {alias} ON {alias}.{ARTIFACT_FK} = p.id AND {alias}.active = true"
        )
        columns.append(
            f"ARRAY_AGG(DISTINCT {alias}.{col}) FILTER (WHERE {alias}.{col} IS NOT NULL) AS {field}"
        )

    where_clauses = ["p.id = ANY($1)"]
    params: list[object] = [ids]
    if active is not None:
        where_clauses.append(f"p.active = ${len(params) + 1}")
        params.append(active)

    query = f"""
        SELECT {", ".join(columns)}
        FROM {TABLE} p
        {" ".join(joins)}
        WHERE {" AND ".join(where_clauses)}
        GROUP BY p.id, p.created_at, p.updated_at, p.generated, p.mcp, p.active
    """

    rows = await conn.fetch(query, *params)

    results = []
    for r in rows:
        data: dict = {
            "id": r["id"],
            "created_at": r["created_at"],
            "updated_at": r["updated_at"],
            "generated": r["generated"],
            "mcp": r["mcp"],
            "active": r["active"],
        }
        for _, _, _, field in JUNCTIONS:
            if field in dict(r):
                data[field] = r[field] or []
        results.append(GetAgentsResponse(**data))

    return results
