"""Profile artifact SEARCH — returns matching profile IDs."""

from uuid import UUID

import asyncpg

from app.infra.search.search_artifact import (
    add_junction_filter,
    execute_artifact_search,
)

TABLE = "profile_artifact"
OWNER_COL = "profile_id"


async def search_profiles(
    conn: asyncpg.Connection,
    *,
    search: str | None = None,
    name_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    email_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    role_ids: list[UUID] | None = None,
    exclude_role_ids: list[UUID] | None = None,
    cohort_ids: list[UUID] | None = None,
    exclude_ids: list[UUID] | None = None,
    active_only: bool = True,
    limit_count: int = 20,
    offset_count: int = 0,
) -> tuple[list[UUID], int]:
    """Search profile artifacts by filters. Returns (IDs, total_count).

    ``role_ids`` is an inclusion filter (profile must carry one of the roles);
    ``exclude_role_ids`` is the negative form (profile must carry none of them)
    and, unlike inclusion, leaves roleless profiles in the result set.
    """
    conditions: list[str] = []
    params: list[object] = []
    idx = 1

    if active_only:
        conditions.append("a.active = true")

    # Text search across name (profile has no descriptions junction)
    if search:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM profile_names_junction nj "
            f"JOIN names_resource nr ON nr.id = nj.names_id "
            f"WHERE nj.{OWNER_COL} = a.id AND nj.active = true "
            f"AND LOWER(nr.name) LIKE '%%' || LOWER(${idx}) || '%%'"
            f")"
        )
        params.append(search)
        idx += 1

    # Junction filters
    if name_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_names_junction",
            owner_col=OWNER_COL,
            resource_col="names_id",
            ids=name_ids,
        )

    if department_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_departments_junction",
            owner_col=OWNER_COL,
            resource_col="departments_id",
            ids=department_ids,
        )

    if email_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_emails_junction",
            owner_col=OWNER_COL,
            resource_col="emails_id",
            ids=email_ids,
        )

    if flag_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_flags_junction",
            owner_col=OWNER_COL,
            resource_col="flags_id",
            ids=flag_ids,
        )

    if profile_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_profiles_junction",
            owner_col=OWNER_COL,
            resource_col="profiles_id",
            ids=profile_ids,
        )

    if role_ids:
        idx = add_junction_filter(
            conditions,
            params,
            idx,
            junction_table="profile_roles_junction",
            owner_col=OWNER_COL,
            resource_col="roles_id",
            ids=role_ids,
        )

    # Negative role filter — exclude profiles that carry any of these roles.
    # Used for role-hierarchy visibility scoping: callers pass the roles
    # strictly above the actor's privilege so those profiles are hidden,
    # while roleless profiles (no junction row) remain visible. Expressed as
    # NOT EXISTS rather than an inclusion filter on the allowed roles, which
    # would also drop name-only/roleless profiles.
    if exclude_role_ids:
        conditions.append(
            f"NOT EXISTS ("
            f"SELECT 1 FROM profile_roles_junction j "
            f"WHERE j.{OWNER_COL} = a.id AND j.active = true "
            f"AND j.roles_id = ANY(${idx})"
            f")"
        )
        params.append(exclude_role_ids)
        idx += 1

    # Cohort filter — 2-hop: profile_artifact → profile_profiles_junction → profiles_resource
    #                        → cohort_profiles_junction → cohort_id
    if cohort_ids:
        conditions.append(
            f"EXISTS ("
            f"SELECT 1 FROM profile_profiles_junction ppj "
            f"JOIN cohort_profiles_junction cpj ON cpj.profiles_id = ppj.profiles_id AND cpj.active = true "
            f"WHERE ppj.{OWNER_COL} = a.id AND ppj.active = true "
            f"AND cpj.cohort_id = ANY(${idx})"
            f")"
        )
        params.append(cohort_ids)
        idx += 1

    # Exclude
    if exclude_ids:
        conditions.append(f"NOT (a.id = ANY(${idx}))")
        params.append(exclude_ids)
        idx += 1

    # Order by name
    order_join = (
        f"LEFT JOIN profile_names_junction pnj ON pnj.{OWNER_COL} = a.id AND pnj.active = true "
        f"LEFT JOIN names_resource nr_sort ON nr_sort.id = pnj.names_id"
    )

    return await execute_artifact_search(
        conn,
        table=TABLE,
        conditions=conditions,
        params=params,
        idx=idx,
        order_join=order_join,
        order_expr="MIN(nr_sort.name) NULLS LAST",
        limit_count=limit_count,
        offset_count=offset_count,
    )
