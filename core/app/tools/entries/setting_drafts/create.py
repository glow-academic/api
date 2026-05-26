"""Setting drafts CREATE — insert entry + connection tables."""

from uuid import UUID

import asyncpg  # type: ignore
from redis.asyncio import Redis

from app.tools.entries.setting_drafts.types import CreateSettingDraftResponse
from app.utils.cache.hedged_row import write_back_row


async def create_setting_draft(
    conn: asyncpg.Connection,
    redis: Redis,
    session_id: UUID,
    *,
    id: UUID | None = None,
    mcp: bool = False,
    soft: bool = False,
    name: str = "",
    system_ids: list[UUID] | None = None,
    auth_item_key_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    color_ids: list[UUID] | None = None,
    department_ids: list[UUID] | None = None,
    description_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    item_ids: list[UUID] | None = None,
    name_ids: list[UUID] | None = None,
    provider_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    threshold_ids: list[UUID] | None = None,
    mcp_ids: list[UUID] | None = None,
    logins_ids: list[UUID] | None = None,
    pending_ids: set[UUID] | None = None,
) -> CreateSettingDraftResponse:
    """Create or update a setting_drafts entry with optional connection links."""

    row = await conn.fetchrow(
        """
        INSERT INTO setting_drafts_entry (id, session_id, active, mcp, generated, name)
        VALUES (COALESCE($5, uuidv7()), $1, $2, $3, true, $4)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id, created_at, active, mcp
        """,
        session_id,
        not soft,
        mcp,
        name,
        id,
    )

    if row is None:
        raise ValueError("Failed to create setting_drafts entry")
    draft_id = row["id"]
    created_at = row["created_at"]
    active_val = row["active"]
    mcp_val = row["mcp"]

    _pending = pending_ids or set()
    connections: list[tuple[str, str, list[UUID]]] = [
        ("setting_drafts_systems_connection", "systems_id", system_ids or []),
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
        ("setting_drafts_providers_connection", "providers_id", provider_ids or []),
        (
            "setting_drafts_provider_keys_connection",
            "provider_keys_id",
            provider_key_ids or [],
        ),
        ("setting_drafts_thresholds_connection", "thresholds_id", threshold_ids or []),
        ("setting_drafts_mcp_connection", "mcp_id", mcp_ids or []),
        ("setting_drafts_logins_connection", "logins_id", logins_ids or []),
    ]

    for table, col, ids in connections:
        for rid in ids:
            await conn.execute(
                f"INSERT INTO {table} (draft_id, {col}, active) VALUES ($1, $2, $3) "
                f"ON CONFLICT (draft_id, {col}) DO UPDATE SET active = EXCLUDED.active",
                draft_id,
                rid,
                False if soft else (rid not in _pending),
            )

    _pending_strs = {str(x) for x in _pending}

    def _active_list(ids: list[UUID]) -> list[str]:
        if soft:
            return []
        return [str(rid) for rid in ids if str(rid) not in _pending_strs]

    def _pending_list(ids: list[UUID]) -> list[str]:
        if soft:
            return [str(rid) for rid in ids]
        return [str(rid) for rid in ids if str(rid) in _pending_strs]

    fresh_row = {
        "id": str(draft_id),
        "created_at": created_at.isoformat(),
        "generated": True,
        "mcp": mcp_val,
        "active": active_val,
        "session_id": str(session_id),
        "name": name,
        "system_ids": _active_list(system_ids or []),
        "auth_item_key_ids": _active_list(auth_item_key_ids or []),
        "auth_ids": _active_list(auth_ids or []),
        "color_ids": _active_list(color_ids or []),
        "department_ids": _active_list(department_ids or []),
        "description_ids": _active_list(description_ids or []),
        "flag_ids": _active_list(flag_ids or []),
        "item_ids": _active_list(item_ids or []),
        "name_ids": _active_list(name_ids or []),
        "provider_ids": _active_list(provider_ids or []),
        "provider_key_ids": _active_list(provider_key_ids or []),
        "threshold_ids": _active_list(threshold_ids or []),
        "mcp_ids": _active_list(mcp_ids or []),
        "logins_ids": _active_list(logins_ids or []),
        "pending_system_ids": _pending_list(system_ids or []),
        "pending_auth_item_key_ids": _pending_list(auth_item_key_ids or []),
        "pending_auth_ids": _pending_list(auth_ids or []),
        "pending_color_ids": _pending_list(color_ids or []),
        "pending_department_ids": _pending_list(department_ids or []),
        "pending_description_ids": _pending_list(description_ids or []),
        "pending_flag_ids": _pending_list(flag_ids or []),
        "pending_item_ids": _pending_list(item_ids or []),
        "pending_name_ids": _pending_list(name_ids or []),
        "pending_provider_ids": _pending_list(provider_ids or []),
        "pending_provider_key_ids": _pending_list(provider_key_ids or []),
        "pending_threshold_ids": _pending_list(threshold_ids or []),
        "pending_mcp_ids": _pending_list(mcp_ids or []),
        "pending_logins_ids": _pending_list(logins_ids or []),
    }
    await write_back_row(
        redis,
        "setting_drafts",
        draft_id,
        fresh_row,
        score_ms=int(created_at.timestamp() * 1000),
    )

    return CreateSettingDraftResponse(id=draft_id)
