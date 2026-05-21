"""Profile drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.profile_drafts.types import GetProfileDraftResponse


async def get_profile_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    redis: Redis,
    active: bool | None = True,
) -> list[GetProfileDraftResponse]:
    """Get profile_drafts entries by IDs with connection data.

    ``active=None`` returns dormant + active rows; used by ack short-circuit
    + auto-accept to reach soft-pending drafts.
    """
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT em.emails_id) FILTER (WHERE em.emails_id IS NOT NULL), '{}') AS email_ids,
            COALESCE(ARRAY_AGG(DISTINCT em.emails_id) FILTER (WHERE em.emails_id IS NOT NULL AND em.active = false), '{}') AS pending_email_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT ro.roles_id) FILTER (WHERE ro.roles_id IS NOT NULL), '{}') AS role_ids
            ,COALESCE(ARRAY_AGG(DISTINCT ro.roles_id) FILTER (WHERE ro.roles_id IS NOT NULL AND ro.active = false), '{}') AS pending_role_ids
            ,COALESCE(ARRAY_AGG(DISTINCT pd.primary_departments_id) FILTER (WHERE pd.primary_departments_id IS NOT NULL), '{}') AS primary_department_ids
            ,COALESCE(ARRAY_AGG(DISTINCT pd.primary_departments_id) FILTER (WHERE pd.primary_departments_id IS NOT NULL AND pd.active = false), '{}') AS pending_primary_department_ids
        FROM profile_drafts_entry d
        LEFT JOIN profile_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN profile_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN profile_drafts_emails_connection em ON em.draft_id = d.id
        LEFT JOIN profile_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN profile_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN profile_drafts_roles_connection ro ON ro.draft_id = d.id
        LEFT JOIN profile_drafts_primary_departments_connection pd ON pd.draft_id = d.id
        WHERE d.id = ANY($1)
          AND ($2::boolean IS NULL OR d.active = $2)
        GROUP BY d.id, d.created_at, d.generated, d.mcp, d.active,
                 d.session_id, d.name
        ORDER BY d.created_at DESC
        """,
        ids,
        active,
    )

    return [
        GetProfileDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            profile_ids=r["profile_ids"],
            department_ids=r["department_ids"],
            email_ids=r["email_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            role_ids=r["role_ids"],
            primary_department_ids=r["primary_department_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_email_ids=r["pending_email_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_role_ids=r["pending_role_ids"],
            pending_primary_department_ids=r["pending_primary_department_ids"],
        )
        for r in rows
    ]
