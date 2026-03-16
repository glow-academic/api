"""Eval drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.eval_drafts.types import GetEvalDraftResponse


async def get_eval_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetEvalDraftResponse]:
    """Get eval_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT m.models_id) FILTER (WHERE m.models_id IS NOT NULL), '{}') AS model_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT r.rubrics_id) FILTER (WHERE r.rubrics_id IS NOT NULL), '{}') AS rubric_ids
        FROM eval_drafts_entry d
        LEFT JOIN eval_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN eval_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN eval_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN eval_drafts_models_connection m ON m.draft_id = d.id
        LEFT JOIN eval_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN eval_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN eval_drafts_rubrics_connection r ON r.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetEvalDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            model_ids=r["model_ids"],
            name_ids=r["name_ids"],
            profile_ids=r["profile_ids"],
            rubric_ids=r["rubric_ids"],
        )
        for r in rows
    ]
