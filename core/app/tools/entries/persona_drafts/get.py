"""Persona drafts GET — read from base table + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.persona_drafts.types import GetPersonaDraftResponse


async def get_persona_drafts(
    conn: asyncpg.Connection,
    ids: list[UUID],
) -> list[GetPersonaDraftResponse]:
    """Get persona_drafts entries by IDs with connection data."""
    if not ids:
        return []

    rows = await conn.fetch(
        """
        SELECT
            d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
            d.group_id, d.session_id,
            COALESCE(ARRAY_AGG(DISTINCT col.colors_id) FILTER (WHERE col.colors_id IS NOT NULL), '{}') AS color_ids,
            COALESCE(ARRAY_AGG(DISTINCT dep.departments_id) FILTER (WHERE dep.departments_id IS NOT NULL), '{}') AS department_ids,
            COALESCE(ARRAY_AGG(DISTINCT desc_c.descriptions_id) FILTER (WHERE desc_c.descriptions_id IS NOT NULL), '{}') AS description_ids,
            COALESCE(ARRAY_AGG(DISTINCT ex.examples_id) FILTER (WHERE ex.examples_id IS NOT NULL), '{}') AS example_ids,
            COALESCE(ARRAY_AGG(DISTINCT f.flags_id) FILTER (WHERE f.flags_id IS NOT NULL), '{}') AS flag_ids,
            COALESCE(ARRAY_AGG(DISTINCT ic.icons_id) FILTER (WHERE ic.icons_id IS NOT NULL), '{}') AS icon_ids,
            COALESCE(ARRAY_AGG(DISTINCT ins.instructions_id) FILTER (WHERE ins.instructions_id IS NOT NULL), '{}') AS instruction_ids,
            COALESCE(ARRAY_AGG(DISTINCT n.names_id) FILTER (WHERE n.names_id IS NOT NULL), '{}') AS name_ids,
            COALESCE(ARRAY_AGG(DISTINCT pf.parameter_fields_id) FILTER (WHERE pf.parameter_fields_id IS NOT NULL), '{}') AS parameter_field_ids,
            COALESCE(ARRAY_AGG(DISTINCT p.profiles_id) FILTER (WHERE p.profiles_id IS NOT NULL), '{}') AS profile_ids,
            COALESCE(ARRAY_AGG(DISTINCT v.voices_id) FILTER (WHERE v.voices_id IS NOT NULL), '{}') AS voice_ids
        FROM persona_drafts_entry d
        LEFT JOIN persona_drafts_colors_connection col ON col.draft_id = d.id
        LEFT JOIN persona_drafts_departments_connection dep ON dep.draft_id = d.id
        LEFT JOIN persona_drafts_descriptions_connection desc_c ON desc_c.draft_id = d.id
        LEFT JOIN persona_drafts_examples_connection ex ON ex.draft_id = d.id
        LEFT JOIN persona_drafts_flags_connection f ON f.draft_id = d.id
        LEFT JOIN persona_drafts_icons_connection ic ON ic.draft_id = d.id
        LEFT JOIN persona_drafts_instructions_connection ins ON ins.draft_id = d.id
        LEFT JOIN persona_drafts_names_connection n ON n.draft_id = d.id
        LEFT JOIN persona_drafts_parameter_fields_connection pf ON pf.draft_id = d.id
        LEFT JOIN persona_drafts_profiles_connection p ON p.draft_id = d.id
        LEFT JOIN persona_drafts_voices_connection v ON v.draft_id = d.id
        WHERE d.id = ANY($1)
          AND d.active = true
        GROUP BY d.id, d.version, d.created_at, d.generated, d.mcp, d.active,
                 d.group_id, d.session_id
        ORDER BY d.created_at DESC
        """,
        ids,
    )

    return [
        GetPersonaDraftResponse(
            id=r["id"],
            version=r["version"],
            created_at=r["created_at"],
            generated=r["generated"],
            mcp=r["mcp"],
            active=r["active"],
            group_id=r["group_id"],
            session_id=r["session_id"],
            color_ids=r["color_ids"],
            department_ids=r["department_ids"],
            description_ids=r["description_ids"],
            example_ids=r["example_ids"],
            flag_ids=r["flag_ids"],
            icon_ids=r["icon_ids"],
            instruction_ids=r["instruction_ids"],
            name_ids=r["name_ids"],
            parameter_field_ids=r["parameter_field_ids"],
            profile_ids=r["profile_ids"],
            voice_ids=r["voice_ids"],
        )
        for r in rows
    ]
