"""Profile artifact GET — reusable data-access layer."""

from uuid import UUID

import asyncpg

from app.tools.artifacts.profile.types import GetProfilesResponse

TABLE = "profile_artifact"
ARTIFACT_FK = "profile_id"

# (flag_name, junction_table, junction_column, response_field)
JUNCTIONS: list[tuple[str, str, str, str]] = [
    ("names", "profile_names_junction", "names_id", "name_ids"),
    ("departments", "profile_departments_junction", "departments_id", "department_ids"),
    ("flags", "profile_flags_junction", "flags_id", "flag_ids"),
    ("emails", "profile_emails_junction", "emails_id", "email_ids"),
    ("profiles", "profile_profiles_junction", "profiles_id", "profile_ids"),
    ("roles", "profile_roles_junction", "roles_id", "role_ids"),
    (
        "primary_departments",
        "profile_primary_departments_junction",
        "primary_departments_id",
        "primary_department_ids",
    ),
]


async def get_profiles(
    conn: asyncpg.Connection,
    ids: list[UUID],
    *,
    active: bool | None = True,
    names: bool = False,
    departments: bool = False,
    flags: bool = False,
    emails: bool = False,
    profiles: bool = False,
    roles: bool = False,
    primary_departments: bool = False,
) -> list[GetProfilesResponse]:
    """Get profile artifacts by IDs with optional junction ID fetching."""
    if not ids:
        return []

    flags_map = {
        "names": names,
        "departments": departments,
        "flags": flags,
        "emails": emails,
        "profiles": profiles,
        "roles": roles,
        "primary_departments": primary_departments,
    }

    active_junctions = [
        (table, col, field) for flag, table, col, field in JUNCTIONS if flags_map[flag]
    ]

    # Build dynamic query. Pre-2026-05: 7-way LEFT JOIN + ARRAY_AGG(DISTINCT)
    # + GROUP BY which produced a cartesian blow-up (3 names × 5 emails × 2
    # roles × ... rows per profile) collapsed by DISTINCT. Measured 11-17ms
    # typical, 140ms tail on warm cache.
    # Now: one correlated subquery per junction. Each hits its own
    # (parent_id, active) index directly — no joins, no cartesian product,
    # no GROUP BY. Same output shape; NULL → [] handled by caller below.
    columns = [
        "p.id",
        "p.created_at",
        "p.updated_at",
        "p.generated",
        "p.mcp",
        "p.active",
    ]

    for table, col, field in active_junctions:
        columns.append(
            f"(SELECT array_agg(DISTINCT {col}) "
            f"FROM {table} "
            f"WHERE {ARTIFACT_FK} = p.id AND active) AS {field}"
        )

    where_clauses = ["p.id = ANY($1)"]
    params: list[object] = [ids]
    if active is not None:
        where_clauses.append(f"p.active = ${len(params) + 1}")
        params.append(active)

    query = f"""
        SELECT {", ".join(columns)}
        FROM {TABLE} p
        WHERE {" AND ".join(where_clauses)}
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
        results.append(GetProfilesResponse(**data))

    return results
