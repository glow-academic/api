"""Setting drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore

from app.tools.entries.setting_drafts.types import CreateSettingDraftResponse


async def create_setting_draft(
    conn: asyncpg.Connection,
    group_id: UUID,
    session_id: UUID,
    *,
    id: UUID | None = None,
    version: int = 0,
    mcp: bool = False,
    soft: bool = False,
    agent_ids: list[UUID] | None = None,
    auth_item_key_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    color_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    threshold_ids: list[UUID] | None = None,
) -> CreateSettingDraftResponse:
    """Create a setting_drafts entry with optional connection table links."""
    draft_id = await conn.fetchval(
        """
        INSERT INTO setting_drafts_entry (id, group_id, session_id, version, active, mcp, generated)
        VALUES (COALESCE($6, uuidv7()), $1, $2, $3, $4, $5, true)
        RETURNING id
        """,
        group_id,
        session_id,
        version,
        not soft,
        mcp,
        id,
    )

    if draft_id is None:
        raise ValueError("Failed to create setting_drafts entry")

    connections: list[tuple[str, str, list[UUID]]] = [
        ("setting_drafts_agents_connection", "agents_id", agent_ids or []),
        (
            "setting_drafts_auth_item_keys_connection",
            "auth_item_keys_id",
            auth_item_key_ids or [],
        ),
        ("setting_drafts_auths_connection", "auths_id", auth_ids or []),
        ("setting_drafts_colors_connection", "colors_id", color_ids or []),
        (
            "setting_drafts_departments_connection",
            "departments_id",
            department_ids or [],
        ),
        (
            "setting_drafts_descriptions_connection",
            "descriptions_id",
            description_ids or [],
        ),
        ("setting_drafts_flags_connection", "flags_id", flag_ids or []),
        ("setting_drafts_items_connection", "items_id", item_ids or []),
        ("setting_drafts_names_connection", "names_id", name_ids or []),
        ("setting_drafts_profiles_connection", "profiles_id", profile_ids or []),
        (
            "setting_drafts_provider_keys_connection",
            "provider_keys_id",
            provider_key_ids or [],
        ),
        ("setting_drafts_thresholds_connection", "thresholds_id", threshold_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}) VALUES ($1, $2)",
                draft_id,
                rid,
            )

    return CreateSettingDraftResponse(id=draft_id)
