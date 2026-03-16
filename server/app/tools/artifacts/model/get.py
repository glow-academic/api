"""Model artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.model.types import GetModelsResponse

TABLE = "model_artifact"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "model_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "model_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "model_departments_junction", "departments_id", "department_ids"),
    ("flags", "model_flags_junction", "flags_id", "flag_ids"),
    ("modalities", "model_modalities_junction", "modalities_id", "modality_ids"),
    ("pricing", "model_pricing_junction", "pricing_id", "pricing_ids"),
    ("providers", "model_providers_junction", "providers_id", "provider_ids"),
    ("qualities", "model_qualities_junction", "qualities_id", "quality_ids"),
    (
        "reasoning_levels",
        "model_reasoning_levels_junction",
        "reasoning_levels_id",
        "reasoning_level_ids",
    ),
    (
        "temperature_levels",
        "model_temperature_levels_junction",
        "temperature_levels_id",
        "temperature_level_ids",
    ),
    ("values", "model_values_junction", "values_id", "value_ids"),
    ("voices", "model_voices_junction", "voices_id", "voice_ids"),
    ("models", "model_models_junction", "models_id", "model_ids"),
]


async def get_models(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    modalities: bool = False,
    pricing: bool = False,
    providers: bool = False,
    qualities: bool = False,
    reasoning_levels: bool = False,
    temperature_levels: bool = False,
    values: bool = False,
    voices: bool = False,
    models: bool = False,
) -> list[GetModelsResponse]:
    """Get model artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "modalities": modalities,
        "pricing": pricing,
        "providers": providers,
        "qualities": qualities,
        "reasoning_levels": reasoning_levels,
        "temperature_levels": temperature_levels,
        "values": values,
        "voices": voices,
        "models": models,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

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
            f"LEFT JOIN {table} {alias} ON {alias}.model_id = p.id AND {alias}.active = true"
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
        results.append(GetModelsResponse(**data))

    return results
