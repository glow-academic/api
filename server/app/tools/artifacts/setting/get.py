"""Setting artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.setting.types import GetSettingsResponse

TABLE = "setting_artifact"
ARTIFACT_FK = "setting_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "setting_names_junction", "names_id", "name_ids"),
    (
        "descriptions",
        "setting_descriptions_junction",
        "descriptions_id",
        "description_ids",
    ),
    ("departments", "setting_departments_junction", "departments_id", "department_ids"),
    ("flags", "setting_flags_junction", "flags_id", "flag_ids"),
    ("colors", "setting_colors_junction", "colors_id", "color_ids"),
    ("profiles", "setting_profiles_junction", "profiles_id", "profile_ids"),
    (
        "auth_item_keys",
        "setting_auth_item_keys_junction",
        "auth_item_keys_id",
        "auth_item_keys_ids",
    ),
    (
        "provider_keys",
        "setting_provider_keys_junction",
        "provider_keys_id",
        "provider_key_ids",
    ),
    ("thresholds", "setting_thresholds_junction", "thresholds_id", "threshold_ids"),
    ("systems", "setting_systems_junction", "systems_id", "systems_ids"),
    ("settings", "setting_settings_junction", "settings_id", "setting_ids"),
    ("auths", "setting_auths_junction", "auths_id", "auth_ids"),
    (
        "auth_item_values",
        "setting_auth_item_values_junction",
        "auth_item_values_id",
        "auth_item_value_ids",
    ),
]


async def get_settings(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    descriptions: bool = False,
    departments: bool = False,
    flags: bool = False,
    colors: bool = False,
    profiles: bool = False,
    auth_item_keys: bool = False,
    provider_keys: bool = False,
    thresholds: bool = False,
    systems: bool = False,
    settings: bool = False,
    auths: bool = False,
    auth_item_values: bool = False,
) -> list[GetSettingsResponse]:
    """Get setting artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "descriptions": descriptions,
        "departments": departments,
        "flags": flags,
        "colors": colors,
        "profiles": profiles,
        "auth_item_keys": auth_item_keys,
        "provider_keys": provider_keys,
        "thresholds": thresholds,
        "systems": systems,
        "settings": settings,
        "auths": auths,
        "auth_item_values": auth_item_values,
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
        results.append(GetSettingsResponse(**data))

    return results
