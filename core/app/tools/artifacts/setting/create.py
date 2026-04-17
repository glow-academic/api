"""Setting artifact CREATE — tool layer."""

from uuid import UUID

import asyncpg

from app.infra.junctions import (
    upsert_multi,
    upsert_single,
)
from app.tools.artifacts.setting.types import CreateSettingResponse

OWNER_COL = "setting_id"

# (junction_table, resource_column, pk_constraint)
SINGLE_JUNCTIONS: list[tuple[str, str, str]] = [
    ("setting_names_junction", "names_id", "setting_names_pkey"),
    ("setting_descriptions_junction", "descriptions_id", "setting_descriptions_pkey"),
]

MULTI_JUNCTIONS: list[tuple[str, str, str]] = [
    ("setting_departments_junction", "departments_id", "setting_departments_pkey"),
    ("setting_auths_junction", "auths_id", "setting_auths_pkey"),
    ("setting_auth_item_keys_junction", "auth_item_keys_id", "setting_auth_item_keys_junction_pkey"),
    ("setting_auth_item_values_junction", "auth_item_values_id", "setting_auth_item_values_junction_pkey"),
    ("setting_colors_junction", "colors_id", "setting_colors_pkey"),
    ("setting_profiles_junction", "profiles_id", "setting_profiles_pkey"),
    ("setting_provider_keys_junction", "provider_keys_id", "setting_provider_keys_junction_pkey"),
    ("setting_systems_junction", "systems_id", "setting_systems_junction_pkey"),
    ("setting_thresholds_junction", "thresholds_id", "setting_thresholds_pkey"),
    ("setting_settings_junction", "settings_id", "setting_settings_junction_pkey"),
]


async def create_setting(
    conn: asyncpg.Connection,
    *,
    id: UUID | None = None,
    name_id: UUID | None = None,
    description_id: UUID | None = None,
    department_ids: list[UUID] | None = None,
    flag_ids: list[UUID] | None = None,
    auth_ids: list[UUID] | None = None,
    auth_item_key_ids: list[UUID] | None = None,
    auth_item_value_ids: list[UUID] | None = None,
    color_ids: list[UUID] | None = None,
    profile_ids: list[UUID] | None = None,
    provider_key_ids: list[UUID] | None = None,
    system_ids: list[UUID] | None = None,
    threshold_ids: list[UUID] | None = None,
    setting_ids: list[UUID] | None = None,
    active: bool | None = None,
    soft: bool = False,
    generated: bool = False,
    mcp: bool = False,
) -> CreateSettingResponse:
    """Create a setting artifact with optional junction links."""
    is_active = not soft if active is None else active
    setting_id: UUID = await conn.fetchval(
        """
        INSERT INTO setting_artifact (id, active, generated, mcp)
        VALUES (COALESCE($4, uuidv7()), $1, $2, $3)
        ON CONFLICT (id) DO UPDATE SET active = EXCLUDED.active
        RETURNING id
        """,
        is_active,
        generated,
        mcp,
        id,
    )

    # Single-select junctions
    single_vals = [name_id, description_id]
    for (table, col, constraint), val in zip(SINGLE_JUNCTIONS, single_vals):
        if val is not None:
            await upsert_single(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=setting_id,
                resource_col=col,
                resource_id=val,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Multi-select junctions (simple)
    multi_vals = [
        department_ids,
        auth_ids,
        auth_item_key_ids,
        auth_item_value_ids,
        color_ids,
        profile_ids,
        provider_key_ids,
        system_ids,
        threshold_ids,
        setting_ids,
    ]
    for (table, col, constraint), vals in zip(MULTI_JUNCTIONS, multi_vals):
        if vals:
            await upsert_multi(
                conn,
                table=table,
                owner_col=OWNER_COL,
                owner_id=setting_id,
                resource_col=col,
                resource_ids=vals,
                constraint=constraint,
                generated=generated,
                mcp=mcp,
                soft=soft,
            )

    # Flags
    if flag_ids:
        await upsert_multi(
            conn,
            table="setting_flags_junction",
            owner_col=OWNER_COL,
            owner_id=setting_id,
            resource_col="flags_id",
            resource_ids=flag_ids,
            constraint="setting_flags_pkey",
            generated=generated,
            mcp=mcp,
            soft=soft,
        )

    return CreateSettingResponse(id=setting_id)
