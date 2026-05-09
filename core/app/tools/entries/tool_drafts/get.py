"""Tool drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.tool_drafts.types import GetToolDraftResponse


async def get_tool_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
    active: bool | None = True,
) -> list[GetToolDraftResponse]:
    """Get tool_drafts entries by IDs with connection data.

    ``active=True`` (default) — only committed drafts.
    ``active=None`` — both committed and dormant pending. Use for
    ack short-circuit / auto-accept lookups.
    """
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.created_at, d.generated, d.mcp, d.active,
            d.session_id,
            d.name,
            COALESCE(ARRAY_AGG(DISTINCT ap.arg_positions_id) FILTER (WHERE ap.arg_positions_id IS NOT NULL), '{}') AS arg_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT ap.arg_positions_id) FILTER (WHERE ap.arg_positions_id IS NOT NULL AND ap.active = false), '{}') AS pending_arg_position_ids,
            COALESCE(ARRAY_AGG(DISTINCT a.args_id) FILTER (WHERE a.args_id IS NOT NULL), '{}') AS arg_ids,
            COALESCE(ARRAY_AGG(DISTINCT a.args_id) FILTER (WHERE a.args_id IS NOT NULL AND a.active = false), '{}') AS pending_arg_ids,
            COALESCE(ARRAY_AGG(DISTINCT ao.args_outputs_id) FILTER (WHERE ao.args_outputs_id IS NOT NULL), '{}') AS args_output_ids,
            COALESCE(ARRAY_AGG(DISTINCT ao.args_outputs_id) FILTER (WHERE ao.args_outputs_id IS NOT NULL AND ao.active = false), '{}') AS pending_args_output_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL AND dep.active = false), '{}') AS pending_department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL AND desc_c.active = false), '{}') AS pending_description_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL AND f.active = false), '{}') AS pending_flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL AND n.active = false), '{}') AS pending_name_ids,
            COALESCE(ARRAY_AGG(DISTINCT perm.permissions_id) FILTER (WHERE perm.permissions_id IS NOT NULL), '{}') AS permission_ids,
            COALESCE(ARRAY_AGG(DISTINCT perm.permissions_id) FILTER (WHERE perm.permissions_id IS NOT NULL AND perm.active = false), '{}') AS pending_permission_ids,
            COALESCE(ARRAY_AGG(DISTINCT ins.instructions_id) FILTER (WHERE ins.instructions_id IS NOT NULL), '{}') AS instruction_ids,
            COALESCE(ARRAY_AGG(DISTINCT ins.instructions_id) FILTER (WHERE ins.instructions_id IS NOT NULL AND ins.active = false), '{}') AS pending_instruction_ids,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL), '{}') AS agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT ag.agents_id) FILTER (WHERE ag.agents_id IS NOT NULL AND ag.active = false), '{}') AS pending_agent_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids
        FROM tool_drafts_entry d
        LEFT JOIN tool_drafts_arg_positions_connection ap ON ap.draft_id = d.id
        LEFT JOIN tool_drafts_args_connection a ON a.draft_id = d.id
        LEFT JOIN tool_drafts_args_outputs_connection ao ON ao.draft_id = d.id
        LEFT JOIN tool_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN tool_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN tool_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN tool_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN tool_drafts_instructions_connection ins ON ins.draft_id = d.id
        LEFT JOIN tool_drafts_permissions_connection perm ON perm.draft_id = d.id
        LEFT JOIN tool_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN tool_drafts_agents_connection ag ON ag.draft_id = d.id
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
        GetToolDraftResponse(
            id=r["id"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            session_id=r["session_id"],
            name=r["name"],
            arg_position_ids=r["arg_position_ids"],
            arg_ids=r["arg_ids"],
            args_output_ids=r["args_output_ids"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            flag_ids=r["flag_ids"],
            name_ids=r["name_ids"],
            instruction_ids=r["instruction_ids"],
            permission_ids=r["permission_ids"],
            profile_ids=r["profile_ids"],
            agent_ids=r["agent_ids"],
            pending_arg_position_ids=r["pending_arg_position_ids"],
            pending_arg_ids=r["pending_arg_ids"],
            pending_args_output_ids=r["pending_args_output_ids"],
            pending_department_ids=r["pending_department_ids"],
            pending_description_ids=r["pending_description_ids"],
            pending_flag_ids=r["pending_flag_ids"],
            pending_name_ids=r["pending_name_ids"],
            pending_permission_ids=r["pending_permission_ids"],
            pending_instruction_ids=r["pending_instruction_ids"],
            pending_agent_ids=r["pending_agent_ids"],
        )
        for r in rows
    ]
