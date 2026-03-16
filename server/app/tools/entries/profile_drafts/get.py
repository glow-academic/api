"""Profile drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.profile_drafts.types import GetProfileDraftResponse


async def get_profile_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetProfileDraftResponse]:
    """Get profile_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT em.emails_id) FILTER (WHERE em.emails_id IS NOT NULL), '{}') AS email_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT rl.request_limits_id) FILTER (WHERE rl.request_limits_id IS NOT NULL), '{}') AS request_limit_ids,
            COALESCE(ARRAY_AGG(DISTINCT ro.roles_id) FILTER (WHERE ro.roles_id IS NOT NULL), '{}') AS role_ids
        FROM profile_drafts_entry d
        LEFT JOIN profile_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN profile_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN profile_drafts_emails_connection em ON em.draft_id = d.id
        LEFT JOIN profile_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN profile_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN profile_drafts_request_limits_connection rl ON rl.draft_id = d.id
        LEFT JOIN profile_drafts_roles_connection ro ON ro.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetProfileDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            profile_ids=r["profile_ids"],
            department_ids=r["department_ids"],
            email_ids=r["email_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            request_limit_ids=r["request_limit_ids"],
            role_ids=r["role_ids"],
        )
        for r in rows
    ]
